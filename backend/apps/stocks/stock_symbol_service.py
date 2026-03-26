"""Port of com.stock.stock.StockSymbolService."""

from __future__ import annotations

import threading
import json
from collections import deque
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from django.core.paginator import Paginator
from django.db.models import Count
from django.utils import timezone

from apps.stocks import stock_queries
from apps.stocks.models import StockHistory, StockIndustryGroup, StockSymbol, StockT0ForeignState
from apps.stocks.history_sync_service import (
    HISTORY_BOOTSTRAP_SESSIONS,
    HISTORY_INCREMENTAL_OVERLAP_DAYS,
    HistorySyncMode,
    resync_ticker_history,
    run_history_sync,
)
from apps.stocks.vps_symbol_sync_service import sync_from_vps as sync_symbols_from_vps
from apps.stock_finance.models import StockFinanceChartSyncJob
from common.exceptions import BadRequestError


@dataclass
class SyncStatus:
    running: bool = False
    received: int = 0
    total_unique: int = 0
    processed: int = 0
    synced: int = 0
    phase: str = "Idle"
    error: str | None = None


@dataclass
class HistorySyncStatus:
    running: bool = False
    mode: HistorySyncMode = HistorySyncMode.INCREMENTAL
    days: int = HISTORY_INCREMENTAL_OVERLAP_DAYS
    total_symbols: int = 0
    processed_symbols: int = 0
    failed_symbols: int = 0
    records_updated: int = 0
    phase: str = "Idle"
    error: str | None = None
    last_failed_ticker: str | None = None


_sync_lock = threading.Lock()
_history_lock = threading.Lock()
_sync_status = SyncStatus()
_history_status = HistorySyncStatus()


def _industry_key(industry_group_id: int | None, industry_group_name: str | None) -> str:
    name = (industry_group_name or "").strip() or "Chua phan loai"
    return f"{industry_group_id if industry_group_id is not None else 0}|{name}"


def _extract_industry_id(key: str) -> int | None:
    idx = key.find("|")
    if idx < 0:
        return None
    try:
        v = int(key[:idx])
        return None if v == 0 else v
    except ValueError:
        return None


def _extract_industry_name(key: str) -> str:
    idx = key.find("|")
    if idx < 0 or idx + 1 >= len(key):
        return key
    return key[idx + 1 :]


def _pct(value: Decimal, total: Decimal) -> Decimal:
    if total is None or total <= 0:
        return Decimal("0")
    return (value * Decimal("100") / total).quantize(Decimal("0.0001"))


def _update_window(queue: deque, value: Decimal, max_size: int, current_sum: Decimal) -> Decimal:
    queue.append(value)
    next_sum = current_sum + value
    if len(queue) > max_size:
        removed = queue.popleft()
        if removed is not None:
            next_sum -= removed
    return next_sum


def _average(sum_val: Decimal, size: int) -> Decimal:
    if size <= 0:
        return Decimal("0")
    return (sum_val / Decimal(size)).quantize(Decimal("0.0001"))


def _decimal_or_zero(value: Any) -> Decimal:
    if value in (None, ""):
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _estimate_foreign_price(history: StockHistory) -> Decimal:
    if history.avg_price and history.avg_price > 0:
        return _decimal_or_zero(history.avg_price)
    if history.close_price and history.close_price > 0:
        return _decimal_or_zero(history.close_price)
    total_val = _decimal_or_zero(history.total_match_val)
    total_vol = int(history.total_match_vol or 0)
    if total_val > 0 and total_vol > 0:
        return (total_val / Decimal(total_vol)).quantize(Decimal("0.0001"))
    return Decimal("0")


def _foreign_values_from_payload(history: StockHistory) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
    raw_payload = (history.raw_payload or "").strip()
    if not raw_payload:
        return None, None, None
    try:
        payload = json.loads(raw_payload)
    except json.JSONDecodeError:
        return None, None, None
    buy_val = _decimal_or_zero(payload.get("foreignBuyValTotal")) if payload.get("foreignBuyValTotal") not in (None, "") else None
    sell_val = _decimal_or_zero(payload.get("foreignSellValTotal")) if payload.get("foreignSellValTotal") not in (None, "") else None
    net_val = _decimal_or_zero(payload.get("netBuySellVal")) if payload.get("netBuySellVal") not in (None, "") else None
    return buy_val, sell_val, net_val


def _serialize_foreign_trading_row(history: StockHistory, symbol: StockSymbol | None = None) -> dict:
    buy_vol_raw = history.foreign_buy_vol_total
    sell_vol_raw = history.foreign_sell_vol_total
    buy_vol = int(buy_vol_raw or 0)
    sell_vol = int(sell_vol_raw or 0)
    net_vol = buy_vol - sell_vol
    estimated_price = _estimate_foreign_price(history)
    payload_buy_val, payload_sell_val, payload_net_val = _foreign_values_from_payload(history)
    has_foreign_volume_data = buy_vol_raw is not None or sell_vol_raw is not None
    if payload_buy_val is not None or payload_sell_val is not None or payload_net_val is not None:
        buy_val = payload_buy_val or Decimal("0")
        sell_val = payload_sell_val or Decimal("0")
        net_val = payload_net_val if payload_net_val is not None else (buy_val - sell_val)
        if buy_val == 0 and sell_val == 0 and buy_vol == 0 and sell_vol == 0:
            value_source = "payload_zero"
        else:
            value_source = "payload"
    else:
        buy_val = (estimated_price * Decimal(buy_vol)).quantize(Decimal("0.0001")) if buy_vol else Decimal("0")
        sell_val = (estimated_price * Decimal(sell_vol)).quantize(Decimal("0.0001")) if sell_vol else Decimal("0")
        net_val = buy_val - sell_val
        value_source = "estimated" if has_foreign_volume_data else "missing"
    industry = symbol.industry_group if symbol else None
    return {
        "ticker": history.ticker,
        "tradingDate": history.trading_date.isoformat(),
        "organName": symbol.organ_name if symbol else None,
        "industryGroupId": industry.id if industry else None,
        "industryGroupName": industry.name if industry else None,
        "foreignBuyVolTotal": buy_vol,
        "foreignSellVolTotal": sell_vol,
        "foreignNetVolTotal": net_vol,
        "foreignEstimatedPrice": estimated_price,
        "foreignBuyValEstimated": buy_val,
        "foreignSellValEstimated": sell_val,
        "foreignNetValEstimated": net_val,
        "foreignValueSource": value_source,
        "hasForeignVolumeData": has_foreign_volume_data,
    }


def _serialize_foreign_t0_row(state: StockT0ForeignState, symbol: StockSymbol | None = None) -> dict:
    industry = symbol.industry_group if symbol else None
    buy_vol = int(state.buy_foreign_qtty or 0)
    sell_vol = int(state.sell_foreign_qtty or 0)
    buy_val = state.buy_foreign_value
    sell_val = state.sell_foreign_value
    if buy_val is None and sell_val is None:
        value_source = "missing"
    elif _decimal_or_zero(buy_val) == 0 and _decimal_or_zero(sell_val) == 0:
        value_source = "payload_zero"
    else:
        value_source = "payload"
    return {
        "ticker": state.ticker,
        "tradingDate": state.trading_date.isoformat(),
        "organName": symbol.organ_name if symbol else None,
        "industryGroupId": industry.id if industry else None,
        "industryGroupName": industry.name if industry else None,
        "foreignBuyVolTotal": buy_vol,
        "foreignSellVolTotal": sell_vol,
        "foreignNetVolTotal": buy_vol - sell_vol,
        "foreignEstimatedPrice": None,
        "foreignBuyValEstimated": _decimal_or_zero(buy_val),
        "foreignSellValEstimated": _decimal_or_zero(sell_val),
        "foreignNetValEstimated": _decimal_or_zero(buy_val) - _decimal_or_zero(sell_val),
        "foreignValueSource": value_source,
        "hasForeignVolumeData": bool(buy_vol or sell_vol),
    }


def _has_positive_foreign_volume(row: dict) -> bool:
    return int(row.get("foreignBuyVolTotal") or 0) > 0 or int(row.get("foreignSellVolTotal") or 0) > 0


def _build_analytics_points(rows: list[dict]) -> list[dict]:
    if not rows:
        return []
    sorted_rows = sorted(rows, key=lambda r: r["trading_date"])
    val5: deque = deque()
    val10: deque = deque()
    val20: deque = deque()
    vol5: deque = deque()
    vol10: deque = deque()
    vol20: deque = deque()
    sum_val5 = sum_val10 = sum_val20 = Decimal("0")
    sum_vol5 = sum_vol10 = sum_vol20 = Decimal("0")
    points = []
    for row in sorted_rows:
        val = row.get("total_match_val") or Decimal("0")
        if not isinstance(val, Decimal):
            val = Decimal(str(val))
        vol_raw = row.get("total_match_vol") or 0
        vol = Decimal(str(vol_raw))
        sum_val5 = _update_window(val5, val, 5, sum_val5)
        sum_val10 = _update_window(val10, val, 10, sum_val10)
        sum_val20 = _update_window(val20, val, 20, sum_val20)
        sum_vol5 = _update_window(vol5, vol, 5, sum_vol5)
        sum_vol10 = _update_window(vol10, vol, 10, sum_vol10)
        sum_vol20 = _update_window(vol20, vol, 20, sum_vol20)
        td = row["trading_date"]
        if hasattr(td, "isoformat"):
            td_out = td.isoformat()
        else:
            td_out = str(td)
        points.append(
            {
                "tradingDate": td_out,
                "totalMatchVal": val,
                "totalMatchVol": int(vol_raw) if vol_raw is not None else 0,
                "avgVal5": _average(sum_val5, len(val5)),
                "avgVal10": _average(sum_val10, len(val10)),
                "avgVal20": _average(sum_val20, len(val20)),
                "avgVol5": _average(sum_vol5, len(vol5)),
                "avgVol10": _average(sum_vol10, len(vol10)),
                "avgVol20": _average(sum_vol20, len(vol20)),
            }
        )
    return points


def get_sync_status() -> dict:
    s = _sync_status
    return {
        "running": s.running,
        "received": s.received,
        "totalUnique": s.total_unique,
        "processed": s.processed,
        "synced": s.synced,
        "phase": s.phase,
        "error": s.error,
    }


def get_history_sync_status() -> dict:
    h = _history_status
    return {
        "running": h.running,
        "mode": h.mode.value,
        "days": h.days,
        "totalSymbols": h.total_symbols,
        "processedSymbols": h.processed_symbols,
        "failedSymbols": h.failed_symbols,
        "recordsUpdated": h.records_updated,
        "phase": h.phase,
        "error": h.error,
        "lastFailedTicker": h.last_failed_ticker,
    }


def _ensure_finance_chart_sync_not_running() -> None:
    active = StockFinanceChartSyncJob.objects.filter(status__in=["RUNNING", "PENDING"]).exists()
    if active:
        raise BadRequestError("Vietstock finance chart sync is running. Please wait until it finishes.")


def sync_from_vps() -> dict:
    global _sync_status
    with _sync_lock:
        if _sync_status.running:
            raise BadRequestError("Stock sync is already running")
        _sync_status = SyncStatus(running=True, phase="Downloading data from VPS")

    try:
        def update_status(
            running: bool,
            received: int,
            total_unique: int,
            processed: int,
            synced: int,
            phase: str,
            error: str | None,
        ) -> None:
            global _sync_status
            _sync_status = SyncStatus(
                running=running,
                received=received,
                total_unique=total_unique,
                processed=processed,
                synced=synced,
                phase=phase,
                error=error,
            )

        return sync_symbols_from_vps(update_status)
    except Exception as ex:
        _sync_status = SyncStatus(False, 0, 0, 0, 0, "Failed", str(ex))
        raise
def list_symbols(page: int, size: int, ticker: str | None, industry_group_id: int | None) -> dict:
    if page < 0:
        raise BadRequestError("Page must be >= 0")
    if size <= 0 or size > 200:
        raise BadRequestError("Size must be between 1 and 200")
    qs = StockSymbol.objects.select_related("industry_group").order_by("ticker")
    nt = (ticker or "").strip().upper()
    if nt:
        qs = qs.filter(ticker__icontains=nt)
    if industry_group_id is not None:
        qs = qs.filter(industry_group_id=industry_group_id)
    paginator = Paginator(qs, size)
    p = paginator.get_page(page + 1)
    tickers = [s.ticker for s in p.object_list]
    counts = (
        StockHistory.objects.filter(ticker__in=tickers)
        .values("ticker")
        .annotate(total=Count("id"))
    )
    count_map = {c["ticker"].upper(): c["total"] for c in counts}
    items = []
    for s in p.object_list:
        ig = s.industry_group
        items.append(
            {
                "id": s.id,
                "ticker": s.ticker,
                "organCode": s.organ_code,
                "organName": s.organ_name,
                "organShortName": s.organ_short_name,
                "icbCode": s.icb_code,
                "icbName2": s.icb_name2,
                "industryGroupId": ig.id if ig else None,
                "industryGroupName": ig.name if ig else None,
                "listingDate": s.listing_date,
                "historyCount": count_map.get(s.ticker.upper(), 0),
            }
        )
    return {
        "items": items,
        "page": page,
        "size": size,
        "totalElements": paginator.count,
        "totalPages": paginator.num_pages,
    }


def list_industry_groups() -> list[dict]:
    return [
        {"id": g.id, "name": g.name}
        for g in StockIndustryGroup.objects.order_by("name")
    ]


def list_tickers() -> list[str]:
    return list(
        StockSymbol.objects.order_by("ticker").values_list("ticker", flat=True).distinct()
    )


def list_history(ticker: str, page: int, size: int) -> dict:
    if not (ticker or "").strip():
        raise BadRequestError("Ticker is required")
    if page < 0:
        raise BadRequestError("Page must be >= 0")
    if size <= 0 or size > 200:
        raise BadRequestError("Size must be between 1 and 200")
    t = ticker.strip().upper()
    qs = StockHistory.objects.filter(ticker=t).order_by("-trading_date")
    paginator = Paginator(qs, size)
    p = paginator.get_page(page + 1)

    def row(h: StockHistory) -> dict:
        return {
            "ticker": h.ticker,
            "tradingDate": h.trading_date.isoformat(),
            "openPrice": h.open_price,
            "highPrice": h.high_price,
            "lowPrice": h.low_price,
            "closePrice": h.close_price,
            "volume": h.volume,
            "avgPrice": h.avg_price,
            "priceChanged": h.price_changed,
            "perPriceChange": h.per_price_change,
            "totalMatchVol": h.total_match_vol,
            "totalMatchVal": h.total_match_val,
            "foreignBuyVolTotal": h.foreign_buy_vol_total,
            "foreignSellVolTotal": h.foreign_sell_vol_total,
        }

    return {
        "items": [row(h) for h in p.object_list],
        "page": page,
        "size": size,
        "totalElements": paginator.count,
        "totalPages": paginator.num_pages,
    }


def list_foreign_trading(page: int, size: int, ticker: str | None, industry_group_id: int | None, trading_date) -> dict:
    if page < 0:
        raise BadRequestError("Page must be >= 0")
    if size <= 0 or size > 200:
        raise BadRequestError("Size must be between 1 and 200")

    normalized_ticker = (ticker or "").strip().upper()
    target_date = trading_date
    history_qs = StockHistory.objects.select_related().order_by("-trading_date", "ticker")
    if normalized_ticker:
        history_qs = history_qs.filter(ticker__icontains=normalized_ticker)
    if target_date is None:
        target_date = history_qs.order_by("-trading_date").values_list("trading_date", flat=True).first()
    symbols_qs = StockSymbol.objects.select_related("industry_group")
    if industry_group_id is not None:
        symbols_qs = symbols_qs.filter(industry_group_id=industry_group_id)
    symbol_map = {item.ticker.upper(): item for item in symbols_qs}
    target_tickers = list(symbol_map.keys()) if industry_group_id is not None else None
    if target_date is not None and target_date == timezone.localdate():
        t0_qs = StockT0ForeignState.objects.filter(trading_date=target_date).order_by("ticker")
        if normalized_ticker:
            t0_qs = t0_qs.filter(ticker__icontains=normalized_ticker)
        if target_tickers is not None:
            t0_qs = t0_qs.filter(ticker__in=target_tickers)
        rows_for_summary = [
            row
            for row in (_serialize_foreign_t0_row(item, symbol_map.get(item.ticker.upper())) for item in t0_qs)
            if _has_positive_foreign_volume(row)
        ]
        paginator = Paginator(rows_for_summary, size)
        p = paginator.get_page(page + 1)
        items = list(p.object_list)
    else:
        qs = history_qs
        if target_date is not None:
            qs = qs.filter(trading_date=target_date)
        if target_tickers is not None:
            qs = qs.filter(ticker__in=target_tickers)
        qs = qs.exclude(foreign_buy_vol_total__isnull=True, foreign_sell_vol_total__isnull=True)
        rows_for_summary = [
            row
            for row in (_serialize_foreign_trading_row(item, symbol_map.get(item.ticker.upper())) for item in qs)
            if _has_positive_foreign_volume(row)
        ]
        paginator = Paginator(rows_for_summary, size)
        p = paginator.get_page(page + 1)
        items = list(p.object_list)

    total_buy_vol = 0
    total_sell_vol = 0
    total_buy_val = Decimal("0")
    total_sell_val = Decimal("0")
    positive_count = 0
    negative_count = 0
    zero_count = 0
    payload_count = 0
    payload_zero_count = 0
    estimated_count = 0
    missing_count = 0

    for row in rows_for_summary:
        total_buy_vol += row["foreignBuyVolTotal"]
        total_sell_vol += row["foreignSellVolTotal"]
        total_buy_val += _decimal_or_zero(row["foreignBuyValEstimated"])
        total_sell_val += _decimal_or_zero(row["foreignSellValEstimated"])
        if row["foreignNetVolTotal"] > 0:
            positive_count += 1
        elif row["foreignNetVolTotal"] < 0:
            negative_count += 1
        else:
            zero_count += 1
        if row["foreignValueSource"] == "payload":
            payload_count += 1
        elif row["foreignValueSource"] == "payload_zero":
            payload_zero_count += 1
        elif row["foreignValueSource"] == "estimated":
            estimated_count += 1
        else:
            missing_count += 1

    return {
        "items": items,
        "page": page,
        "size": size,
        "totalElements": paginator.count,
        "totalPages": paginator.num_pages,
        "summary": {
            "tradingDate": target_date.isoformat() if hasattr(target_date, "isoformat") else None,
            "totalBuyVol": total_buy_vol,
            "totalSellVol": total_sell_vol,
            "totalNetVol": total_buy_vol - total_sell_vol,
            "totalBuyValEstimated": total_buy_val,
            "totalSellValEstimated": total_sell_val,
            "totalNetValEstimated": total_buy_val - total_sell_val,
            "positiveCount": positive_count,
            "negativeCount": negative_count,
            "zeroCount": zero_count,
            "payloadCount": payload_count,
            "payloadZeroCount": payload_zero_count,
            "estimatedCount": estimated_count,
            "missingCount": missing_count,
        },
    }


def get_foreign_trading_ticker_timeline(ticker: str, page: int, size: int, trading_date_from, trading_date_to) -> dict:
    normalized_ticker = (ticker or "").strip().upper()
    if not normalized_ticker:
        raise BadRequestError("Ticker is required")
    if page < 0:
        raise BadRequestError("Page must be >= 0")
    if size <= 0 or size > 400:
        raise BadRequestError("Size must be between 1 and 400")

    qs = StockHistory.objects.filter(ticker=normalized_ticker).order_by("-trading_date")
    if trading_date_from is not None:
        qs = qs.filter(trading_date__gte=trading_date_from)
    if trading_date_to is not None:
        qs = qs.filter(trading_date__lte=trading_date_to)
    qs = qs.exclude(foreign_buy_vol_total__isnull=True, foreign_sell_vol_total__isnull=True)

    paginator = Paginator(qs, size)
    p = paginator.get_page(page + 1)
    symbol = StockSymbol.objects.select_related("industry_group").filter(ticker__iexact=normalized_ticker).first()
    items = [_serialize_foreign_trading_row(history, symbol) for history in p.object_list]
    return {
        "ticker": normalized_ticker,
        "page": page,
        "size": size,
        "totalElements": paginator.count,
        "totalPages": paginator.num_pages,
        "items": items,
    }


def analytics_by_industry(industry_group_id: int | None) -> dict:
    rows = stock_queries.aggregate_industry_daily(industry_group_id)
    label = "Tat ca nganh"
    if industry_group_id is not None:
        ig = StockIndustryGroup.objects.filter(pk=industry_group_id).first()
        label = ig.name if ig else f"Industry #{industry_group_id}"
    return {"seriesType": "industry", "label": label, "points": _build_analytics_points(rows)}


def analytics_by_ticker(ticker: str) -> dict:
    if not (ticker or "").strip():
        raise BadRequestError("Ticker is required")
    t = ticker.strip().upper()
    rows = stock_queries.aggregate_ticker_daily(t)
    return {"seriesType": "ticker", "label": t, "points": _build_analytics_points(rows)}


def analytics_industry_allocation(top_n: int) -> dict:
    if top_n <= 0 or top_n > 20:
        raise BadRequestError("topN must be between 1 and 20")
    rows = stock_queries.aggregate_industry_allocation_daily()
    if not rows:
        return {"topN": top_n, "legends": [], "legendNames": [], "points": []}

    total_by_industry: dict[str, Decimal] = {}
    for row in rows:
        key = _industry_key(row.get("industry_group_id"), row.get("industry_group_name"))
        val = row.get("total_match_val") or Decimal("0")
        if not isinstance(val, Decimal):
            val = Decimal(str(val))
        total_by_industry[key] = total_by_industry.get(key, Decimal("0")) + val

    top_keys = sorted(total_by_industry.keys(), key=lambda k: total_by_industry[k], reverse=True)[:top_n]
    top_set = set(top_keys)

    values_by_date: dict[Any, dict[str, Decimal]] = {}
    for row in rows:
        td = row["trading_date"]
        key = _industry_key(row.get("industry_group_id"), row.get("industry_group_name"))
        val = row.get("total_match_val") or Decimal("0")
        if not isinstance(val, Decimal):
            val = Decimal(str(val))
        values_by_date.setdefault(td, {})[key] = values_by_date.get(td, {}).get(key, Decimal("0")) + val

    points_out = []
    for td, by_ind in sorted(values_by_date.items(), key=lambda x: x[0]):
        day_total = sum(by_ind.values(), Decimal("0"))
        allocations = []
        top_total = Decimal("0")
        for k in top_keys:
            v = by_ind.get(k, Decimal("0"))
            top_total += v
            allocations.append(
                {
                    "industryGroupId": _extract_industry_id(k),
                    "industryGroupName": _extract_industry_name(k),
                    "totalMatchVal": v,
                    "percentage": _pct(v, day_total),
                    "weightPct": _pct(v, day_total),
                }
            )
        others = day_total - top_total
        if others > 0:
            allocations.append(
                {
                    "industryGroupId": None,
                    "industryGroupName": "Khac",
                    "totalMatchVal": others,
                    "percentage": _pct(others, day_total),
                    "weightPct": _pct(others, day_total),
                }
            )
        td_out = td.isoformat() if hasattr(td, "isoformat") else str(td)
        points_out.append({"tradingDate": td_out, "allocations": allocations})

    legends = [_extract_industry_name(k) for k in top_keys]
    if any(
        a["industryGroupName"] == "Khac" for p in points_out for a in p["allocations"]
    ):
        legends.append("Khac")

    return {"topN": top_n, "legends": legends, "legendNames": legends, "points": points_out}


def analytics_ticker_allocation(ticker: str, top_n: int) -> dict:
    if top_n <= 0 or top_n > 20:
        raise BadRequestError("topN must be between 1 and 20")
    if not (ticker or "").strip():
        raise BadRequestError("Ticker is required")
    t = ticker.strip().upper()
    sym = StockSymbol.objects.filter(ticker__iexact=t).select_related("industry_group").first()
    if not sym:
        raise BadRequestError("Ticker not found")

    ig_id = sym.industry_group_id
    icb = (sym.icb_code or "").strip()
    ig = sym.industry_group
    industry_label = None
    if ig:
        industry_label = f"{ig.name} (#{ig_id})"
    elif sym.icb_name2 and sym.icb_name2.strip():
        industry_label = sym.icb_name2.strip() + (f" ({icb})" if icb else "")
    elif icb:
        industry_label = f"Ma nganh {icb}"

    if ig_id is None and not icb:
        return {"topN": top_n, "industryLabel": industry_label, "legends": [], "legendNames": [], "points": []}

    rows = (
        stock_queries.aggregate_ticker_allocation_by_industry(ig_id)
        if ig_id is not None
        else stock_queries.aggregate_ticker_allocation_by_icb(icb)
    )
    if not rows:
        return {"topN": top_n, "industryLabel": industry_label, "legends": [], "legendNames": [], "points": []}

    total_by_ticker: dict[str, Decimal] = {}
    for row in rows:
        tk = row["ticker"]
        val = row.get("total_match_val") or Decimal("0")
        if not isinstance(val, Decimal):
            val = Decimal(str(val))
        total_by_ticker[tk] = total_by_ticker.get(tk, Decimal("0")) + val

    top_tickers = sorted(total_by_ticker.keys(), key=lambda k: total_by_ticker[k], reverse=True)[:top_n]

    values_by_date: dict[Any, dict[str, Decimal]] = {}
    for row in rows:
        td = row["trading_date"]
        tk = row["ticker"]
        val = row.get("total_match_val") or Decimal("0")
        if not isinstance(val, Decimal):
            val = Decimal(str(val))
        values_by_date.setdefault(td, {})[tk] = values_by_date.get(td, {}).get(tk, Decimal("0")) + val

    points_out = []
    for td, by_t in sorted(values_by_date.items(), key=lambda x: x[0]):
        day_total = sum(by_t.values(), Decimal("0"))
        allocations = []
        top_total = Decimal("0")
        for tk in top_tickers:
            v = by_t.get(tk, Decimal("0"))
            top_total += v
            allocations.append(
                {
                    "ticker": tk,
                    "totalMatchVal": v,
                    "percentage": _pct(v, day_total),
                    "weightPct": _pct(v, day_total),
                }
            )
        others = day_total - top_total
        if others > 0:
            allocations.append(
                {
                    "ticker": "Khac",
                    "totalMatchVal": others,
                    "percentage": _pct(others, day_total),
                    "weightPct": _pct(others, day_total),
                }
            )
        td_out = td.isoformat() if hasattr(td, "isoformat") else str(td)
        points_out.append({"tradingDate": td_out, "allocations": allocations})

    legends = list(top_tickers)
    if any(a["ticker"] == "Khac" for p in points_out for a in p["allocations"]):
        legends.append("Khac")

    return {"topN": top_n, "industryLabel": industry_label, "legends": legends, "legendNames": legends, "points": points_out}


def _run_history_sync(mode: HistorySyncMode) -> None:
    global _history_status
    try:
        def update_status(
            running: bool,
            status_mode: HistorySyncMode,
            days: int,
            total_symbols: int,
            processed_symbols: int,
            failed_symbols: int,
            records_updated: int,
            phase: str,
            error: str | None,
            last_failed_ticker: str | None,
        ) -> None:
            global _history_status
            _history_status = HistorySyncStatus(
                running=running,
                mode=status_mode,
                days=days,
                total_symbols=total_symbols,
                processed_symbols=processed_symbols,
                failed_symbols=failed_symbols,
                records_updated=records_updated,
                phase=phase,
                error=error,
                last_failed_ticker=last_failed_ticker,
            )

        run_history_sync(mode, update_status)
    except Exception as ex:
        _history_status = HistorySyncStatus(
            False,
            mode,
            _history_status.days,
            _history_status.total_symbols,
            _history_status.processed_symbols,
            _history_status.failed_symbols,
            _history_status.records_updated,
            "Failed",
            str(ex),
            _history_status.last_failed_ticker,
        )


def start_history_sync() -> dict:
    global _history_status
    with _history_lock:
        if _history_status.running:
            raise BadRequestError("Stock history sync is already running")
        _ensure_finance_chart_sync_not_running()
        _history_status = HistorySyncStatus(
            True,
            HistorySyncMode.INCREMENTAL,
            HISTORY_INCREMENTAL_OVERLAP_DAYS,
            0,
            0,
            0,
            0,
            "Queued",
            None,
        )
        threading.Thread(target=_run_history_sync, args=(HistorySyncMode.INCREMENTAL,), daemon=True).start()
    return get_history_sync_status()


def start_history_reset_sync() -> dict:
    global _history_status
    with _history_lock:
        if _history_status.running:
            raise BadRequestError("Stock history sync is already running")
        _ensure_finance_chart_sync_not_running()
        _history_status = HistorySyncStatus(
            True,
            HistorySyncMode.RESET,
            HISTORY_BOOTSTRAP_SESSIONS,
            0,
            0,
            0,
            0,
            "Queued",
            None,
        )
        threading.Thread(target=_run_history_sync, args=(HistorySyncMode.RESET,), daemon=True).start()
    return get_history_sync_status()


def resync_history_for_ticker(ticker: str) -> dict:
    global _history_status
    normalized_ticker = (ticker or "").strip().upper()
    with _history_lock:
        if _history_status.running:
            raise BadRequestError("Stock history sync is already running")
        _ensure_finance_chart_sync_not_running()
        _history_status = HistorySyncStatus(
            True,
            HistorySyncMode.RESET,
            HISTORY_BOOTSTRAP_SESSIONS,
            1,
            0,
            0,
            0,
            f"Resyncing {normalized_ticker}",
            None,
            None,
        )

    try:
        def update_status(
            running: bool,
            status_mode: HistorySyncMode,
            days: int,
            total_symbols: int,
            processed_symbols: int,
            failed_symbols: int,
            records_updated: int,
            phase: str,
            error: str | None,
            last_failed_ticker: str | None,
        ) -> None:
            global _history_status
            _history_status = HistorySyncStatus(
                running=running,
                mode=status_mode,
                days=days,
                total_symbols=total_symbols,
                processed_symbols=processed_symbols,
                failed_symbols=failed_symbols,
                records_updated=records_updated,
                phase=phase,
                error=error,
                last_failed_ticker=last_failed_ticker,
            )

        return resync_ticker_history(normalized_ticker, update_status)
    except ValueError as ex:
        _history_status = HistorySyncStatus(
            False,
            HistorySyncMode.RESET,
            HISTORY_BOOTSTRAP_SESSIONS,
            1,
            0,
            1,
            0,
            "Failed",
            str(ex),
            normalized_ticker,
        )
        raise BadRequestError(str(ex)) from ex
    except Exception as ex:
        _history_status = HistorySyncStatus(
            False,
            HistorySyncMode.RESET,
            HISTORY_BOOTSTRAP_SESSIONS,
            1,
            0,
            1,
            0,
            "Failed",
            str(ex),
            normalized_ticker,
        )
        raise
