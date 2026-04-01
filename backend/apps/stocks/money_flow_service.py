from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from django.core.paginator import Paginator
from django.db import connection
from django.utils import timezone

from apps.settings_app import services as setting_services
from apps.stocks.models import MoneyFlowDailyClose, MoneyFlowFeatureSnapshot, StockHistory, StockSymbol, StockT0Snapshot
from common.exceptions import BadRequestError

MONEY_FLOW_ENTITY_STOCK = "stock"
MONEY_FLOW_ENTITY_SECTOR = "sector"
MONEY_FLOW_ENTITY_MARKET = "market"
MONEY_FLOW_WINDOW_SLOT = "slot"
MONEY_FLOW_WINDOW_EOD = "eod"
MONEY_FLOW_MARKET_GLOBAL_ID = "GLOBAL"


@dataclass
class BaselineResult:
    value: Decimal | None
    days_used: int
    low_history_confidence: bool


def _coerce_decimal(value: Any) -> Decimal:
    if value in (None, ""):
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _safe_div(numerator: Any, denominator: Any) -> Decimal | None:
    denom = _coerce_decimal(denominator)
    if denom == 0:
        return None
    return _coerce_decimal(numerator) / denom


def _payload_decimal(payload: dict[str, Any], key: str) -> Decimal | None:
    value = payload.get(key)
    if value in (None, ""):
        return None
    return _coerce_decimal(value)


def _serialize_feature(entity: MoneyFlowFeatureSnapshot) -> dict[str, Any]:
    try:
        payload = json.loads(entity.feature_payload or "{}")
    except json.JSONDecodeError:
        payload = {}
    return {
        "id": entity.id,
        "entityType": entity.entity_type,
        "entityId": entity.entity_id,
        "tradingDate": entity.trading_date.isoformat(),
        "windowType": entity.window_type,
        "snapshotSlot": entity.snapshot_slot or None,
        "asOfAt": entity.as_of_at.isoformat() if entity.as_of_at else None,
        "historyDaysUsed": int(entity.history_days_used or 0),
        "historyBaselineDays": int(entity.history_baseline_days or 0),
        "historyMinDaysForStable": int(entity.history_min_days_for_stable or 0),
        "lowHistoryConfidence": bool(entity.low_history_confidence),
        "features": payload,
        "updatedAt": entity.updated_at.isoformat() if entity.updated_at else None,
    }


def _money_flow_config() -> dict[str, Any]:
    return setting_services.get_money_flow_feature_config()


def _baseline_from_values(values: list[Decimal], baseline_days: int, min_days: int, allow_partial: bool) -> BaselineResult:
    picked = values[:baseline_days]
    days_used = len(picked)
    if days_used == 0:
        return BaselineResult(None, 0, True)
    if days_used < min_days and not allow_partial:
        return BaselineResult(None, days_used, True)
    return BaselineResult(
        value=sum(picked, Decimal("0")) / Decimal(days_used),
        days_used=days_used,
        low_history_confidence=days_used < min_days,
    )


def _rank_map(values: list[tuple[str, Decimal | None]]) -> dict[str, int | None]:
    ordered = sorted(values, key=lambda item: (item[1] is None, -(item[1] or Decimal("-9999999"))))
    output: dict[str, int | None] = {}
    rank = 0
    for key, value in ordered:
        if value is None:
            output[key] = None
            continue
        rank += 1
        output[key] = rank
    return output


def _ensure_money_flow_tables() -> None:
    vendor = connection.vendor
    if vendor == "postgresql":
        daily_close_sql = """
        CREATE TABLE IF NOT EXISTS money_flow_daily_close (
            id BIGSERIAL PRIMARY KEY,
            ticker VARCHAR(20) NOT NULL,
            trading_date DATE NOT NULL,
            snapshot_slot VARCHAR(5) NOT NULL,
            snapshot_at TIMESTAMPTZ NOT NULL,
            active_buy_val NUMERIC(24,4) NULL,
            active_sell_val NUMERIC(24,4) NULL,
            active_buy_vol BIGINT NULL,
            active_sell_vol BIGINT NULL,
            net_flow_val NUMERIC(24,4) NULL,
            net_flow_vol BIGINT NULL,
            total_match_val NUMERIC(24,4) NULL,
            total_match_vol BIGINT NULL,
            raw_payload TEXT NULL,
            created_at TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL,
            CONSTRAINT money_flow_daily_close_ticker_date_uniq UNIQUE (ticker, trading_date)
        )
        """
        feature_sql = """
        CREATE TABLE IF NOT EXISTS money_flow_feature_snapshots (
            id BIGSERIAL PRIMARY KEY,
            entity_type VARCHAR(20) NOT NULL,
            entity_id VARCHAR(100) NOT NULL,
            trading_date DATE NOT NULL,
            window_type VARCHAR(20) NOT NULL,
            snapshot_slot VARCHAR(5) NULL,
            as_of_at TIMESTAMPTZ NOT NULL,
            feature_payload TEXT NULL,
            history_days_used INTEGER NULL,
            history_baseline_days INTEGER NULL,
            history_min_days_for_stable INTEGER NULL,
            low_history_confidence BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL,
            CONSTRAINT money_flow_feature_snapshots_uniq UNIQUE (entity_type, entity_id, trading_date, window_type, snapshot_slot)
        )
        """
    else:
        daily_close_sql = """
        CREATE TABLE IF NOT EXISTS money_flow_daily_close (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker VARCHAR(20) NOT NULL,
            trading_date DATE NOT NULL,
            snapshot_slot VARCHAR(5) NOT NULL,
            snapshot_at DATETIME NOT NULL,
            active_buy_val NUMERIC(24,4) NULL,
            active_sell_val NUMERIC(24,4) NULL,
            active_buy_vol BIGINT NULL,
            active_sell_vol BIGINT NULL,
            net_flow_val NUMERIC(24,4) NULL,
            net_flow_vol BIGINT NULL,
            total_match_val NUMERIC(24,4) NULL,
            total_match_vol BIGINT NULL,
            raw_payload TEXT NULL,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            UNIQUE (ticker, trading_date)
        )
        """
        feature_sql = """
        CREATE TABLE IF NOT EXISTS money_flow_feature_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_type VARCHAR(20) NOT NULL,
            entity_id VARCHAR(100) NOT NULL,
            trading_date DATE NOT NULL,
            window_type VARCHAR(20) NOT NULL,
            snapshot_slot VARCHAR(5) NULL,
            as_of_at DATETIME NOT NULL,
            feature_payload TEXT NULL,
            history_days_used INTEGER NULL,
            history_baseline_days INTEGER NULL,
            history_min_days_for_stable INTEGER NULL,
            low_history_confidence BOOLEAN NOT NULL DEFAULT 0,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            UNIQUE (entity_type, entity_id, trading_date, window_type, snapshot_slot)
        )
        """
    with connection.cursor() as cursor:
        cursor.execute(daily_close_sql)
        cursor.execute(feature_sql)


def _history_stock_slot_baseline(ticker: str, snapshot_slot: str) -> BaselineResult:
    config = _money_flow_config()
    rows = list(
        StockT0Snapshot.objects.filter(ticker=ticker, snapshot_slot=snapshot_slot)
        .order_by("-trading_date")
        .values_list("trading_date", "active_buy_val", "active_sell_val")
    )
    values: list[Decimal] = []
    seen_dates: set[date] = set()
    for trading_date, active_buy_val, active_sell_val in rows:
        if trading_date in seen_dates:
            continue
        seen_dates.add(trading_date)
        values.append(abs(_coerce_decimal(active_buy_val) - _coerce_decimal(active_sell_val)))
    return _baseline_from_values(
        values,
        int(config["historyBaselineDays"]),
        int(config["historyMinDaysForStable"]),
        bool(config["historyAllowPartialBaseline"]),
    )


def _history_stock_eod_baseline(ticker: str) -> BaselineResult:
    config = _money_flow_config()
    rows = list(MoneyFlowDailyClose.objects.filter(ticker=ticker).order_by("-trading_date").values_list("trading_date", "net_flow_val"))
    values: list[Decimal] = []
    seen_dates: set[date] = set()
    for trading_date, net_flow_val in rows:
        if trading_date in seen_dates:
            continue
        seen_dates.add(trading_date)
        values.append(abs(_coerce_decimal(net_flow_val)))
    return _baseline_from_values(
        values,
        int(config["historyBaselineDays"]),
        int(config["historyMinDaysForStable"]),
        bool(config["historyAllowPartialBaseline"]),
    )


def _history_payload_baseline(entity_type: str, entity_id: str, window_type: str, snapshot_slot: str | None, payload_key: str) -> BaselineResult:
    config = _money_flow_config()
    qs = MoneyFlowFeatureSnapshot.objects.filter(entity_type=entity_type, entity_id=entity_id, window_type=window_type).order_by("-trading_date")
    if snapshot_slot is not None:
        qs = qs.filter(snapshot_slot=snapshot_slot)
    rows = list(qs.values_list("trading_date", "feature_payload"))
    values: list[Decimal] = []
    seen_dates: set[date] = set()
    for trading_date, feature_payload in rows:
        if trading_date in seen_dates:
            continue
        seen_dates.add(trading_date)
        try:
            payload = json.loads(feature_payload or "{}")
        except json.JSONDecodeError:
            payload = {}
        value = _payload_decimal(payload, payload_key)
        if value is not None:
            values.append(abs(value))
    return _baseline_from_values(
        values,
        int(config["historyBaselineDays"]),
        int(config["historyMinDaysForStable"]),
        bool(config["historyAllowPartialBaseline"]),
    )


def _history_share_baseline(entity_type: str, entity_id: str, window_type: str, snapshot_slot: str | None, payload_key: str) -> BaselineResult:
    config = _money_flow_config()
    qs = MoneyFlowFeatureSnapshot.objects.filter(entity_type=entity_type, entity_id=entity_id, window_type=window_type).order_by("-trading_date")
    if snapshot_slot is not None:
        qs = qs.filter(snapshot_slot=snapshot_slot)
    rows = list(qs.values_list("trading_date", "feature_payload"))
    values: list[Decimal] = []
    seen_dates: set[date] = set()
    for trading_date, feature_payload in rows:
        if trading_date in seen_dates:
            continue
        seen_dates.add(trading_date)
        try:
            payload = json.loads(feature_payload or "{}")
        except json.JSONDecodeError:
            payload = {}
        value = _payload_decimal(payload, payload_key)
        if value is not None:
            values.append(value)
    return _baseline_from_values(
        values,
        int(config["historyBaselineDays"]),
        int(config["historyMinDaysForStable"]),
        bool(config["historyAllowPartialBaseline"]),
    )


def capture_money_flow_daily_close(trading_date: date) -> dict[str, Any]:
    _ensure_money_flow_tables()
    now = timezone.now()
    rows = list(StockT0Snapshot.objects.filter(trading_date=trading_date).order_by("ticker", "-snapshot_slot"))
    latest_by_ticker: dict[str, StockT0Snapshot] = {}
    for row in rows:
        latest_by_ticker.setdefault(row.ticker.upper(), row)
    count = 0
    for ticker, row in latest_by_ticker.items():
        raw_payload = {
            "snapshotSlot": row.snapshot_slot,
            "snapshotAt": row.snapshot_at.isoformat() if row.snapshot_at else None,
            "activeBuyVal": str(_coerce_decimal(row.active_buy_val)),
            "activeSellVal": str(_coerce_decimal(row.active_sell_val)),
            "activeBuyVol": int(row.active_buy_vol or 0),
            "activeSellVol": int(row.active_sell_vol or 0),
            "totalMatchVal": str(_coerce_decimal(row.total_match_val)),
            "totalMatchVol": int(row.total_match_vol or 0),
        }
        MoneyFlowDailyClose.objects.update_or_create(
            ticker=ticker,
            trading_date=trading_date,
            defaults={
                "snapshot_slot": row.snapshot_slot,
                "snapshot_at": row.snapshot_at or now,
                "active_buy_val": row.active_buy_val,
                "active_sell_val": row.active_sell_val,
                "active_buy_vol": row.active_buy_vol,
                "active_sell_vol": row.active_sell_vol,
                "net_flow_val": _coerce_decimal(row.active_buy_val) - _coerce_decimal(row.active_sell_val),
                "net_flow_vol": int(row.active_buy_vol or 0) - int(row.active_sell_vol or 0),
                "total_match_val": row.total_match_val,
                "total_match_vol": row.total_match_vol,
                "raw_payload": json.dumps(raw_payload, ensure_ascii=False),
                "created_at": now,
                "updated_at": now,
            },
        )
        count += 1
    return {"tradingDate": trading_date.isoformat(), "count": count}


def _build_stock_slot_payload(snapshot: StockT0Snapshot) -> tuple[dict[str, Any], int, bool]:
    net_flow_val = _coerce_decimal(snapshot.active_buy_val) - _coerce_decimal(snapshot.active_sell_val)
    active_net_share = _safe_div(net_flow_val, snapshot.total_match_val)
    net_flow_baseline = _history_stock_slot_baseline(snapshot.ticker, snapshot.snapshot_slot)
    share_baseline = _history_share_baseline(MONEY_FLOW_ENTITY_STOCK, snapshot.ticker.upper(), MONEY_FLOW_WINDOW_SLOT, snapshot.snapshot_slot, "activeNetShare")
    payload = {
        "ticker": snapshot.ticker.upper(),
        "snapshotSlot": snapshot.snapshot_slot,
        "netFlowVal": net_flow_val,
        "netFlowVol": int(snapshot.active_buy_vol or 0) - int(snapshot.active_sell_vol or 0),
        "activeBuyShare": _safe_div(snapshot.active_buy_val, snapshot.total_match_val),
        "activeSellShare": _safe_div(snapshot.active_sell_val, snapshot.total_match_val),
        "activeNetShare": active_net_share,
        "avgAbsNetFlowHistSlot": net_flow_baseline.value,
        "netFlowRatioSlot": _safe_div(net_flow_val, net_flow_baseline.value) if net_flow_baseline.value else None,
        "avgActiveNetShareHistSlot": share_baseline.value,
        "activeNetShareDeltaSlot": (active_net_share - share_baseline.value) if active_net_share is not None and share_baseline.value is not None else None,
    }
    return payload, max(net_flow_baseline.days_used, share_baseline.days_used), bool(net_flow_baseline.low_history_confidence or share_baseline.low_history_confidence)


def rebuild_money_flow_slot_features(snapshot_slot: str, trading_date: date) -> dict[str, Any]:
    _ensure_money_flow_tables()
    now = timezone.now()
    config = _money_flow_config()
    baseline_days = int(config["historyBaselineDays"])
    min_days = int(config["historyMinDaysForStable"])
    snapshots = list(StockT0Snapshot.objects.filter(trading_date=trading_date, snapshot_slot=snapshot_slot).order_by("ticker"))
    symbols = {
        row.ticker.upper(): row
        for row in StockSymbol.objects.select_related("industry_group").filter(ticker__in=[item.ticker for item in snapshots])
    }
    stock_payloads: list[tuple[str, dict[str, Any], int, bool, str | None]] = []
    sector_rollup: dict[str, dict[str, Any]] = {}
    market_net_flow_val = Decimal("0")
    market_total_match_val = Decimal("0")
    for snapshot in snapshots:
        payload, history_days_used, low_confidence = _build_stock_slot_payload(snapshot)
        symbol = symbols.get(snapshot.ticker.upper())
        sector_id = str(symbol.industry_group_id) if symbol and symbol.industry_group_id else None
        payload["industryGroupId"] = int(sector_id) if sector_id else None
        stock_payloads.append((snapshot.ticker.upper(), payload, history_days_used, low_confidence, sector_id))
        market_net_flow_val += _coerce_decimal(payload["netFlowVal"])
        market_total_match_val += _coerce_decimal(snapshot.total_match_val)
        if sector_id is None:
            continue
        bucket = sector_rollup.setdefault(sector_id, {"netFlowVal": Decimal("0"), "totalMatchVal": Decimal("0")})
        bucket["netFlowVal"] += _coerce_decimal(payload["netFlowVal"])
        bucket["totalMatchVal"] += _coerce_decimal(snapshot.total_match_val)

    market_baseline = _history_payload_baseline(MONEY_FLOW_ENTITY_MARKET, MONEY_FLOW_MARKET_GLOBAL_ID, MONEY_FLOW_WINDOW_SLOT, snapshot_slot, "marketNetFlowVal")
    market_ratio = _safe_div(market_net_flow_val, market_baseline.value) if market_baseline.value else None
    market_payload = {
        "marketNetFlowVal": market_net_flow_val,
        "marketActiveNetShare": _safe_div(market_net_flow_val, market_total_match_val),
        "marketNetFlowRatioGlobalSlot": market_ratio,
    }
    MoneyFlowFeatureSnapshot.objects.update_or_create(
        entity_type=MONEY_FLOW_ENTITY_MARKET,
        entity_id=MONEY_FLOW_MARKET_GLOBAL_ID,
        trading_date=trading_date,
        window_type=MONEY_FLOW_WINDOW_SLOT,
        snapshot_slot=snapshot_slot,
        defaults={
            "as_of_at": now,
            "feature_payload": json.dumps(market_payload, ensure_ascii=False, default=str),
            "history_days_used": market_baseline.days_used,
            "history_baseline_days": baseline_days,
            "history_min_days_for_stable": min_days,
            "low_history_confidence": market_baseline.low_history_confidence,
            "created_at": now,
            "updated_at": now,
        },
    )

    sector_ratios: dict[str, Decimal | None] = {}
    sector_market_strengths: dict[str, Decimal | None] = {}
    for sector_id, aggregate in sector_rollup.items():
        sector_baseline = _history_payload_baseline(MONEY_FLOW_ENTITY_SECTOR, sector_id, MONEY_FLOW_WINDOW_SLOT, snapshot_slot, "sectorNetFlowVal")
        sector_ratio = _safe_div(aggregate["netFlowVal"], sector_baseline.value) if sector_baseline.value else None
        sector_ratios[sector_id] = sector_ratio
        sector_market_strengths[sector_id] = (sector_ratio - market_ratio) if sector_ratio is not None and market_ratio is not None else None
        payload = {
            "industryGroupId": int(sector_id),
            "sectorNetFlowVal": aggregate["netFlowVal"],
            "sectorActiveNetShare": _safe_div(aggregate["netFlowVal"], aggregate["totalMatchVal"]),
            "sectorNetFlowRatioSlot": sector_ratio,
            "sectorVsMarketStrengthSlot": sector_market_strengths[sector_id],
        }
        MoneyFlowFeatureSnapshot.objects.update_or_create(
            entity_type=MONEY_FLOW_ENTITY_SECTOR,
            entity_id=sector_id,
            trading_date=trading_date,
            window_type=MONEY_FLOW_WINDOW_SLOT,
            snapshot_slot=snapshot_slot,
            defaults={
                "as_of_at": now,
                "feature_payload": json.dumps(payload, ensure_ascii=False, default=str),
                "history_days_used": sector_baseline.days_used,
                "history_baseline_days": baseline_days,
                "history_min_days_for_stable": min_days,
                "low_history_confidence": sector_baseline.low_history_confidence,
                "created_at": now,
                "updated_at": now,
            },
        )

    stock_market_strengths: list[tuple[str, Decimal | None]] = []
    stock_sector_strengths_by_sector: dict[str, list[tuple[str, Decimal | None]]] = {}
    for ticker, payload, history_days_used, low_confidence, sector_id in stock_payloads:
        stock_ratio = _payload_decimal(payload, "netFlowRatioSlot")
        sector_ratio = sector_ratios.get(sector_id or "")
        payload["stockVsMarketStrengthSlot"] = (stock_ratio - market_ratio) if stock_ratio is not None and market_ratio is not None else None
        payload["stockVsSectorStrengthSlot"] = (stock_ratio - sector_ratio) if stock_ratio is not None and sector_ratio is not None else None
        stock_market_strengths.append((ticker, _payload_decimal(payload, "stockVsMarketStrengthSlot")))
        if sector_id:
            stock_sector_strengths_by_sector.setdefault(sector_id, []).append((ticker, _payload_decimal(payload, "stockVsSectorStrengthSlot")))
        MoneyFlowFeatureSnapshot.objects.update_or_create(
            entity_type=MONEY_FLOW_ENTITY_STOCK,
            entity_id=ticker,
            trading_date=trading_date,
            window_type=MONEY_FLOW_WINDOW_SLOT,
            snapshot_slot=snapshot_slot,
            defaults={
                "as_of_at": now,
                "feature_payload": json.dumps(payload, ensure_ascii=False, default=str),
                "history_days_used": history_days_used,
                "history_baseline_days": baseline_days,
                "history_min_days_for_stable": min_days,
                "low_history_confidence": low_confidence,
                "created_at": now,
                "updated_at": now,
            },
        )

    market_rank_map = _rank_map(stock_market_strengths)
    sector_leadership_map: dict[str, int | None] = {}
    for sector_id, entries in stock_sector_strengths_by_sector.items():
        sector_leadership_map.update(_rank_map(entries))
    sector_rank_map = _rank_map(list(sector_market_strengths.items()))

    for entity in MoneyFlowFeatureSnapshot.objects.filter(trading_date=trading_date, window_type=MONEY_FLOW_WINDOW_SLOT, snapshot_slot=snapshot_slot):
        try:
            payload = json.loads(entity.feature_payload or "{}")
        except json.JSONDecodeError:
            payload = {}
        if entity.entity_type == MONEY_FLOW_ENTITY_STOCK:
            payload["marketStrengthRankSlot"] = market_rank_map.get(entity.entity_id)
            payload["sectorLeadershipRankSlot"] = sector_leadership_map.get(entity.entity_id)
        elif entity.entity_type == MONEY_FLOW_ENTITY_SECTOR:
            payload["marketStrengthRankSlot"] = sector_rank_map.get(entity.entity_id)
        entity.feature_payload = json.dumps(payload, ensure_ascii=False, default=str)
        entity.updated_at = now
        entity.save(update_fields=["feature_payload", "updated_at"])

    return {"tradingDate": trading_date.isoformat(), "snapshotSlot": snapshot_slot, "stocks": len(stock_payloads), "sectors": len(sector_rollup)}


def rebuild_money_flow_eod_features(trading_date: date) -> dict[str, Any]:
    _ensure_money_flow_tables()
    now = timezone.now()
    config = _money_flow_config()
    baseline_days = int(config["historyBaselineDays"])
    min_days = int(config["historyMinDaysForStable"])
    daily_closes = list(MoneyFlowDailyClose.objects.filter(trading_date=trading_date).order_by("ticker"))
    if not daily_closes:
        return {"tradingDate": trading_date.isoformat(), "stocks": 0, "sectors": 0}
    histories = {row.ticker.upper(): row for row in StockHistory.objects.filter(trading_date=trading_date, ticker__in=[item.ticker for item in daily_closes])}
    symbols = {row.ticker.upper(): row for row in StockSymbol.objects.select_related("industry_group").filter(ticker__in=[item.ticker for item in daily_closes])}
    stock_payloads: list[tuple[str, dict[str, Any], int, bool, str | None]] = []
    sector_rollup: dict[str, dict[str, Any]] = {}
    market_net_flow_val = Decimal("0")
    market_total_match_val = Decimal("0")
    for daily_close in daily_closes:
        history = histories.get(daily_close.ticker.upper())
        net_flow_baseline = _history_stock_eod_baseline(daily_close.ticker)
        share_baseline = _history_share_baseline(MONEY_FLOW_ENTITY_STOCK, daily_close.ticker.upper(), MONEY_FLOW_WINDOW_EOD, None, "activeNetShareEod")
        active_net_share_eod = _safe_div(daily_close.net_flow_val, daily_close.total_match_val)
        total_match_val_eod = _coerce_decimal(history.total_match_val) if history is not None else _coerce_decimal(daily_close.total_match_val)
        total_match_vol_eod = int(history.total_match_vol or 0) if history is not None else int(daily_close.total_match_vol or 0)
        payload = {
            "ticker": daily_close.ticker.upper(),
            "netFlowValEod": _coerce_decimal(daily_close.net_flow_val),
            "netFlowVolEod": int(daily_close.net_flow_vol or 0),
            "activeNetShareEod": active_net_share_eod,
            "avgAbsNetFlowHistEod": net_flow_baseline.value,
            "netFlowRatioEod": _safe_div(daily_close.net_flow_val, net_flow_baseline.value) if net_flow_baseline.value else None,
            "avgActiveNetShareHistEod": share_baseline.value,
            "activeNetShareDeltaEod": (active_net_share_eod - share_baseline.value) if active_net_share_eod is not None and share_baseline.value is not None else None,
            "totalMatchValEod": total_match_val_eod,
            "totalMatchVolEod": total_match_vol_eod,
            "usesHistoryEod": history is not None,
        }
        symbol = symbols.get(daily_close.ticker.upper())
        sector_id = str(symbol.industry_group_id) if symbol and symbol.industry_group_id else None
        payload["industryGroupId"] = int(sector_id) if sector_id else None
        stock_payloads.append((daily_close.ticker.upper(), payload, max(net_flow_baseline.days_used, share_baseline.days_used), bool(net_flow_baseline.low_history_confidence or share_baseline.low_history_confidence), sector_id))
        market_net_flow_val += _coerce_decimal(payload["netFlowValEod"])
        market_total_match_val += _coerce_decimal(payload["totalMatchValEod"])
        if sector_id is None:
            continue
        bucket = sector_rollup.setdefault(sector_id, {"netFlowValEod": Decimal("0"), "totalMatchValEod": Decimal("0")})
        bucket["netFlowValEod"] += _coerce_decimal(payload["netFlowValEod"])
        bucket["totalMatchValEod"] += _coerce_decimal(payload["totalMatchValEod"])

    market_baseline = _history_payload_baseline(MONEY_FLOW_ENTITY_MARKET, MONEY_FLOW_MARKET_GLOBAL_ID, MONEY_FLOW_WINDOW_EOD, None, "marketNetFlowValEod")
    market_ratio = _safe_div(market_net_flow_val, market_baseline.value) if market_baseline.value else None
    MoneyFlowFeatureSnapshot.objects.update_or_create(
            entity_type=MONEY_FLOW_ENTITY_MARKET,
            entity_id=MONEY_FLOW_MARKET_GLOBAL_ID,
            trading_date=trading_date,
            window_type=MONEY_FLOW_WINDOW_EOD,
            snapshot_slot="",
        defaults={
            "as_of_at": now,
            "feature_payload": json.dumps(
                {
                    "marketNetFlowValEod": market_net_flow_val,
                    "marketActiveNetShareEod": _safe_div(market_net_flow_val, market_total_match_val),
                    "marketNetFlowRatioGlobalEod": market_ratio,
                },
                ensure_ascii=False,
                default=str,
            ),
            "history_days_used": market_baseline.days_used,
            "history_baseline_days": baseline_days,
            "history_min_days_for_stable": min_days,
            "low_history_confidence": market_baseline.low_history_confidence,
            "created_at": now,
            "updated_at": now,
        },
    )
    sector_ratios: dict[str, Decimal | None] = {}
    sector_market_strengths: dict[str, Decimal | None] = {}
    for sector_id, aggregate in sector_rollup.items():
        sector_baseline = _history_payload_baseline(MONEY_FLOW_ENTITY_SECTOR, sector_id, MONEY_FLOW_WINDOW_EOD, None, "sectorNetFlowValEod")
        sector_ratio = _safe_div(aggregate["netFlowValEod"], sector_baseline.value) if sector_baseline.value else None
        sector_ratios[sector_id] = sector_ratio
        sector_market_strengths[sector_id] = (sector_ratio - market_ratio) if sector_ratio is not None and market_ratio is not None else None
        MoneyFlowFeatureSnapshot.objects.update_or_create(
            entity_type=MONEY_FLOW_ENTITY_SECTOR,
            entity_id=sector_id,
            trading_date=trading_date,
            window_type=MONEY_FLOW_WINDOW_EOD,
            snapshot_slot="",
            defaults={
                "as_of_at": now,
                "feature_payload": json.dumps(
                    {
                        "industryGroupId": int(sector_id),
                        "sectorNetFlowValEod": aggregate["netFlowValEod"],
                        "sectorActiveNetShareEod": _safe_div(aggregate["netFlowValEod"], aggregate["totalMatchValEod"]),
                        "sectorNetFlowRatioEod": sector_ratio,
                        "sectorVsMarketStrengthEod": sector_market_strengths[sector_id],
                    },
                    ensure_ascii=False,
                    default=str,
                ),
                "history_days_used": sector_baseline.days_used,
                "history_baseline_days": baseline_days,
                "history_min_days_for_stable": min_days,
                "low_history_confidence": sector_baseline.low_history_confidence,
                "created_at": now,
                "updated_at": now,
            },
        )
    stock_market_strengths: list[tuple[str, Decimal | None]] = []
    stock_sector_strengths_by_sector: dict[str, list[tuple[str, Decimal | None]]] = {}
    for ticker, payload, history_days_used, low_confidence, sector_id in stock_payloads:
        stock_ratio = _payload_decimal(payload, "netFlowRatioEod")
        sector_ratio = sector_ratios.get(sector_id or "")
        payload["stockVsMarketStrengthEod"] = (stock_ratio - market_ratio) if stock_ratio is not None and market_ratio is not None else None
        payload["stockVsSectorStrengthEod"] = (stock_ratio - sector_ratio) if stock_ratio is not None and sector_ratio is not None else None
        stock_market_strengths.append((ticker, _payload_decimal(payload, "stockVsMarketStrengthEod")))
        if sector_id:
            stock_sector_strengths_by_sector.setdefault(sector_id, []).append((ticker, _payload_decimal(payload, "stockVsSectorStrengthEod")))
        MoneyFlowFeatureSnapshot.objects.update_or_create(
            entity_type=MONEY_FLOW_ENTITY_STOCK,
            entity_id=ticker,
            trading_date=trading_date,
            window_type=MONEY_FLOW_WINDOW_EOD,
            snapshot_slot="",
            defaults={
                "as_of_at": now,
                "feature_payload": json.dumps(payload, ensure_ascii=False, default=str),
                "history_days_used": history_days_used,
                "history_baseline_days": baseline_days,
                "history_min_days_for_stable": min_days,
                "low_history_confidence": low_confidence,
                "created_at": now,
                "updated_at": now,
            },
        )
    market_rank_map = _rank_map(stock_market_strengths)
    sector_leadership_map: dict[str, int | None] = {}
    for sector_id, entries in stock_sector_strengths_by_sector.items():
        sector_leadership_map.update(_rank_map(entries))
    sector_rank_map = _rank_map(list(sector_market_strengths.items()))
    for entity in MoneyFlowFeatureSnapshot.objects.filter(trading_date=trading_date, window_type=MONEY_FLOW_WINDOW_EOD, snapshot_slot=""):
        try:
            payload = json.loads(entity.feature_payload or "{}")
        except json.JSONDecodeError:
            payload = {}
        if entity.entity_type == MONEY_FLOW_ENTITY_STOCK:
            payload["marketStrengthRankEod"] = market_rank_map.get(entity.entity_id)
            payload["sectorLeadershipRankEod"] = sector_leadership_map.get(entity.entity_id)
        elif entity.entity_type == MONEY_FLOW_ENTITY_SECTOR:
            payload["marketStrengthRankEod"] = sector_rank_map.get(entity.entity_id)
        entity.feature_payload = json.dumps(payload, ensure_ascii=False, default=str)
        entity.updated_at = now
        entity.save(update_fields=["feature_payload", "updated_at"])
    return {"tradingDate": trading_date.isoformat(), "stocks": len(stock_payloads), "sectors": len(sector_rollup)}


def list_money_flow_features(
    page: int,
    size: int,
    entity_type: str | None,
    trading_date: date | None,
    window_type: str | None,
    snapshot_slot: str | None,
    entity_id: str | None,
) -> dict[str, Any]:
    _ensure_money_flow_tables()
    if page < 0:
        raise BadRequestError("Page must be >= 0")
    if size <= 0 or size > 200:
        raise BadRequestError("Size must be between 1 and 200")
    qs = MoneyFlowFeatureSnapshot.objects.order_by("-trading_date", "entity_type", "entity_id", "window_type", "snapshot_slot")
    if entity_type:
        qs = qs.filter(entity_type=entity_type)
    if trading_date is not None:
        qs = qs.filter(trading_date=trading_date)
    if window_type:
        qs = qs.filter(window_type=window_type)
    if snapshot_slot:
        qs = qs.filter(snapshot_slot=snapshot_slot)
    if entity_id:
        qs = qs.filter(entity_id=entity_id)
    paginator = Paginator(qs, size)
    current = paginator.get_page(page + 1)
    return {
        "items": [_serialize_feature(item) for item in current.object_list],
        "page": page,
        "size": size,
        "totalElements": paginator.count,
        "totalPages": paginator.num_pages,
    }


def rebuild_money_flow_features(trading_date: date, snapshot_slot: str | None = None, include_eod: bool = True) -> dict[str, Any]:
    slot_result = rebuild_money_flow_slot_features(snapshot_slot, trading_date) if snapshot_slot else None
    eod_result = None
    if include_eod:
        capture_money_flow_daily_close(trading_date)
        eod_result = rebuild_money_flow_eod_features(trading_date)
    return {"tradingDate": trading_date.isoformat(), "slot": slot_result, "eod": eod_result}


def backfill_money_flow_eod(trading_date_from: date | None = None, trading_date_to: date | None = None) -> dict[str, Any]:
    _ensure_money_flow_tables()
    qs = StockT0Snapshot.objects.order_by().values_list("trading_date", flat=True).distinct()
    if trading_date_from is not None:
        qs = qs.filter(trading_date__gte=trading_date_from)
    if trading_date_to is not None:
        qs = qs.filter(trading_date__lte=trading_date_to)
    trading_dates = sorted(qs)
    results: list[dict[str, Any]] = []
    total_daily_close = 0
    total_stocks = 0
    total_sectors = 0
    for trading_date in trading_dates:
        captured = capture_money_flow_daily_close(trading_date)
        rebuilt = rebuild_money_flow_eod_features(trading_date)
        total_daily_close += int(captured.get("count", 0))
        total_stocks += int(rebuilt.get("stocks", 0))
        total_sectors += int(rebuilt.get("sectors", 0))
        results.append(
            {
                "tradingDate": trading_date.isoformat(),
                "dailyCloseCount": int(captured.get("count", 0)),
                "stockCount": int(rebuilt.get("stocks", 0)),
                "sectorCount": int(rebuilt.get("sectors", 0)),
            }
        )
    return {
        "tradingDateFrom": trading_date_from.isoformat() if trading_date_from else None,
        "tradingDateTo": trading_date_to.isoformat() if trading_date_to else None,
        "dates": results,
        "totalDates": len(results),
        "totalDailyClose": total_daily_close,
        "totalStocks": total_stocks,
        "totalSectors": total_sectors,
    }


def backfill_money_flow_slot(trading_date_from: date | None = None, trading_date_to: date | None = None) -> dict[str, Any]:
    _ensure_money_flow_tables()
    qs = StockT0Snapshot.objects.order_by().values_list("trading_date", flat=True).distinct()
    if trading_date_from is not None:
        qs = qs.filter(trading_date__gte=trading_date_from)
    if trading_date_to is not None:
        qs = qs.filter(trading_date__lte=trading_date_to)
    trading_dates = sorted(qs)
    results: list[dict[str, Any]] = []
    total_slots = 0
    total_stocks = 0
    total_sectors = 0
    for trading_date in trading_dates:
        slots = sorted(
            StockT0Snapshot.objects.filter(trading_date=trading_date)
            .order_by()
            .values_list("snapshot_slot", flat=True)
            .distinct()
        )
        slot_results: list[dict[str, Any]] = []
        for snapshot_slot in slots:
            rebuilt = rebuild_money_flow_slot_features(snapshot_slot, trading_date)
            slot_results.append(
                {
                    "snapshotSlot": snapshot_slot,
                    "stockCount": int(rebuilt.get("stocks", 0)),
                    "sectorCount": int(rebuilt.get("sectors", 0)),
                }
            )
            total_slots += 1
            total_stocks += int(rebuilt.get("stocks", 0))
            total_sectors += int(rebuilt.get("sectors", 0))
        results.append(
            {
                "tradingDate": trading_date.isoformat(),
                "slots": slot_results,
                "slotCount": len(slot_results),
            }
        )
    return {
        "tradingDateFrom": trading_date_from.isoformat() if trading_date_from else None,
        "tradingDateTo": trading_date_to.isoformat() if trading_date_to else None,
        "dates": results,
        "totalDates": len(results),
        "totalSlots": total_slots,
        "totalStocks": total_stocks,
        "totalSectors": total_sectors,
    }
