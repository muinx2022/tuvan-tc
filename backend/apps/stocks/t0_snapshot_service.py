from __future__ import annotations

import asyncio
import hmac
import hashlib
import json
import logging
import os
import socket
import time
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time as dt_time, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

import msgpack
import websockets
from asgiref.sync import sync_to_async
from django.core.paginator import Paginator
from django.db import connection, transaction
from django.db.models import Count
from django.utils import timezone

from apps.settings_app.models import AppSetting
from apps.settings_app import services as setting_services
from apps.stocks.models import StockSymbol, StockT0ForeignState, StockT0RealtimeState, StockT0Snapshot
from common.exceptions import BadRequestError

logger = logging.getLogger(__name__)

T0_TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")
T0_DEFAULT_TIMES = ["09:15", "10:00", "11:00", "11:30", "13:00", "14:00", "14:30", "14:45", "15:00"]
T0_LOCK_TTL_SECONDS = 90
T0_SNAPSHOT_GRACE_SECONDS = 120
T0_PROACTIVE_RECONNECT_SECONDS = (7 * 60 * 60) + (45 * 60)
DNSE_WS_URL = "wss://ws-openapi.dnse.com.vn"
T0_TRADING_SESSIONS = [
    (dt_time(hour=9, minute=15), dt_time(hour=11, minute=30)),
    (dt_time(hour=13, minute=0), dt_time(hour=15, minute=0)),
]


async def _run_sync(func, *args, **kwargs):
    return await sync_to_async(func, thread_sensitive=True)(*args, **kwargs)


def _ensure_t0_tables() -> None:
    vendor = connection.vendor
    if vendor == "postgresql":
        realtime_sql = """
        CREATE TABLE IF NOT EXISTS stock_t0_realtime_state (
            id BIGSERIAL PRIMARY KEY,
            ticker VARCHAR(20) NOT NULL UNIQUE,
            trading_date DATE NOT NULL,
            last_message_at TIMESTAMPTZ NOT NULL,
            total_match_vol BIGINT NULL,
            total_match_val NUMERIC(24,4) NULL,
            raw_payload TEXT NULL,
            created_at TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL
        )
        """
        foreign_sql = """
        CREATE TABLE IF NOT EXISTS stock_t0_foreign_state (
            id BIGSERIAL PRIMARY KEY,
            ticker VARCHAR(20) NOT NULL,
            trading_date DATE NOT NULL,
            source_exchange VARCHAR(20) NULL,
            buy_foreign_qtty BIGINT NULL,
            sell_foreign_qtty BIGINT NULL,
            buy_foreign_value NUMERIC(24,4) NULL,
            sell_foreign_value NUMERIC(24,4) NULL,
            fetched_at TIMESTAMPTZ NOT NULL,
            raw_payload TEXT NULL,
            created_at TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL,
            CONSTRAINT stock_t0_foreign_state_ticker_date_uniq UNIQUE (ticker, trading_date)
        )
        """
        snapshot_sql = """
        CREATE TABLE IF NOT EXISTS stock_t0_snapshots (
            id BIGSERIAL PRIMARY KEY,
            ticker VARCHAR(20) NOT NULL,
            trading_date DATE NOT NULL,
            snapshot_slot VARCHAR(5) NOT NULL,
            snapshot_at TIMESTAMPTZ NOT NULL,
            total_match_vol BIGINT NULL,
            total_match_val NUMERIC(24,4) NULL,
            raw_payload TEXT NULL,
            created_at TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL,
            CONSTRAINT stock_t0_snapshots_ticker_date_slot_uniq UNIQUE (ticker, trading_date, snapshot_slot)
        )
        """
    else:
        realtime_sql = """
        CREATE TABLE IF NOT EXISTS stock_t0_realtime_state (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker VARCHAR(20) NOT NULL UNIQUE,
            trading_date DATE NOT NULL,
            last_message_at DATETIME NOT NULL,
            total_match_vol BIGINT NULL,
            total_match_val NUMERIC(24,4) NULL,
            raw_payload TEXT NULL,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL
        )
        """
        foreign_sql = """
        CREATE TABLE IF NOT EXISTS stock_t0_foreign_state (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker VARCHAR(20) NOT NULL,
            trading_date DATE NOT NULL,
            source_exchange VARCHAR(20) NULL,
            buy_foreign_qtty BIGINT NULL,
            sell_foreign_qtty BIGINT NULL,
            buy_foreign_value NUMERIC(24,4) NULL,
            sell_foreign_value NUMERIC(24,4) NULL,
            fetched_at DATETIME NOT NULL,
            raw_payload TEXT NULL,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            UNIQUE (ticker, trading_date)
        )
        """
        snapshot_sql = """
        CREATE TABLE IF NOT EXISTS stock_t0_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker VARCHAR(20) NOT NULL,
            trading_date DATE NOT NULL,
            snapshot_slot VARCHAR(5) NOT NULL,
            snapshot_at DATETIME NOT NULL,
            total_match_vol BIGINT NULL,
            total_match_val NUMERIC(24,4) NULL,
            raw_payload TEXT NULL,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            UNIQUE (ticker, trading_date, snapshot_slot)
        )
        """
    with connection.cursor() as cursor:
        cursor.execute(realtime_sql)
        cursor.execute(foreign_sql)
        cursor.execute(snapshot_sql)
        existing_columns: set[str] = set()
        if vendor == "postgresql":
            cursor.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'stock_t0_snapshots'
                """
            )
            existing_columns = {row[0] for row in cursor.fetchall()}
        else:
            cursor.execute("PRAGMA table_info(stock_t0_snapshots)")
            existing_columns = {row[1] for row in cursor.fetchall()}

        alter_statements = {
            "foreign_buy_vol_total": "ALTER TABLE stock_t0_snapshots ADD COLUMN foreign_buy_vol_total BIGINT NULL",
            "foreign_sell_vol_total": "ALTER TABLE stock_t0_snapshots ADD COLUMN foreign_sell_vol_total BIGINT NULL",
            "foreign_buy_val_total": "ALTER TABLE stock_t0_snapshots ADD COLUMN foreign_buy_val_total NUMERIC(24,4) NULL",
            "foreign_sell_val_total": "ALTER TABLE stock_t0_snapshots ADD COLUMN foreign_sell_val_total NUMERIC(24,4) NULL",
            "net_foreign_vol": "ALTER TABLE stock_t0_snapshots ADD COLUMN net_foreign_vol BIGINT NULL",
            "net_foreign_val": "ALTER TABLE stock_t0_snapshots ADD COLUMN net_foreign_val NUMERIC(24,4) NULL",
            "foreign_data_source": "ALTER TABLE stock_t0_snapshots ADD COLUMN foreign_data_source VARCHAR(30) NULL",
        }
        for column_name, sql in alter_statements.items():
            if column_name not in existing_columns:
                cursor.execute(sql)


def _today_vn() -> date:
    return timezone.now().astimezone(T0_TIMEZONE).date()


def _now_vn() -> datetime:
    return timezone.now().astimezone(T0_TIMEZONE)


def _parse_slot(value: str) -> dt_time:
    hour, minute = value.split(":")
    return dt_time(hour=int(hour), minute=int(minute))


def _valid_ticker(value: str | None) -> bool:
    ticker = (value or "").strip().upper()
    return len(ticker) == 3 and ticker.isalpha()


def list_valid_t0_tickers() -> list[str]:
    tickers = StockSymbol.objects.order_by("ticker").values_list("ticker", flat=True).distinct()
    return [ticker.strip().upper() for ticker in tickers if _valid_ticker(ticker)]


def _serialize_snapshot(entity: StockT0Snapshot) -> dict:
    return {
        "id": entity.id,
        "ticker": entity.ticker,
        "tradingDate": entity.trading_date.isoformat(),
        "snapshotSlot": entity.snapshot_slot,
        "snapshotAt": entity.snapshot_at.isoformat() if entity.snapshot_at else None,
        "totalMatchVol": int(entity.total_match_vol or 0),
        "totalMatchVal": entity.total_match_val,
        "foreignBuyVolTotal": int(entity.foreign_buy_vol_total or 0),
        "foreignSellVolTotal": int(entity.foreign_sell_vol_total or 0),
        "foreignBuyValTotal": entity.foreign_buy_val_total,
        "foreignSellValTotal": entity.foreign_sell_val_total,
        "netForeignVol": int(entity.net_foreign_vol or 0),
        "netForeignVal": entity.net_foreign_val,
        "foreignDataSource": entity.foreign_data_source,
        "hasRawPayload": bool((entity.raw_payload or "").strip()),
        "rawPayload": entity.raw_payload,
        "updatedAt": entity.updated_at.isoformat() if entity.updated_at else None,
    }


def _serialize_realtime(entity: StockT0RealtimeState) -> dict:
    return {
        "ticker": entity.ticker,
        "tradingDate": entity.trading_date.isoformat(),
        "lastMessageAt": entity.last_message_at.isoformat() if entity.last_message_at else None,
        "totalMatchVol": int(entity.total_match_vol or 0),
        "totalMatchVal": entity.total_match_val,
        "rawPayload": entity.raw_payload,
    }


def _serialize_foreign_state(entity: StockT0ForeignState) -> dict:
    buy_vol = int(entity.buy_foreign_qtty or 0)
    sell_vol = int(entity.sell_foreign_qtty or 0)
    buy_val = _coerce_decimal(entity.buy_foreign_value)
    sell_val = _coerce_decimal(entity.sell_foreign_value)
    return {
        "ticker": entity.ticker,
        "tradingDate": entity.trading_date.isoformat(),
        "sourceExchange": entity.source_exchange,
        "foreignBuyVolTotal": buy_vol,
        "foreignSellVolTotal": sell_vol,
        "foreignBuyValTotal": buy_val,
        "foreignSellValTotal": sell_val,
        "netForeignVol": buy_vol - sell_vol,
        "netForeignVal": buy_val - sell_val,
        "fetchedAt": entity.fetched_at.isoformat() if entity.fetched_at else None,
        "rawPayload": entity.raw_payload,
    }


def _coerce_decimal(value: Any) -> Decimal:
    if value in (None, ""):
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _config_value(config: dict[str, Any], key: str, default: Any) -> Any:
    value = config.get(key)
    return default if value is None else value


def _mask_api_key(value: str | None) -> str | None:
    raw = (value or "").strip()
    if not raw:
        return None
    if len(raw) <= 6:
        return f"{raw[:2]}***"
    return f"{raw[:4]}***{raw[-2:]}"


def _extract_trade_totals(payload: dict[str, Any]) -> tuple[int, Decimal]:
    total_match_vol = payload.get("tvt")
    if total_match_vol in (None, ""):
        total_match_vol = payload.get("total_volume_traded")
    if total_match_vol in (None, ""):
        total_match_vol = payload.get("TotalVolumeTraded")
    total_match_val = payload.get("gta")
    if total_match_val in (None, ""):
        total_match_val = payload.get("gross_trade_amount")
    if total_match_val in (None, ""):
        total_match_val = payload.get("GrossTradeAmount")
    return int(total_match_vol or 0), _coerce_decimal(total_match_val)


def _slot_index(slot: str | None) -> int:
    if not slot:
        return -1
    try:
        return T0_DEFAULT_TIMES.index(slot)
    except ValueError:
        return -1


def _projection_slot_for(snapshot_slot: str | None, projection_slots: list[str]) -> str | None:
    current_index = _slot_index(snapshot_slot)
    if current_index < 0:
        return None
    eligible = [slot for slot in projection_slots if _slot_index(slot) <= current_index]
    return eligible[-1] if eligible else None


def _minutes_of_slot(slot: str) -> int:
    parsed = _parse_slot(slot)
    return parsed.hour * 60 + parsed.minute


def _projection_bounds_for(snapshot_slot: str | None, projection_slots: list[str]) -> tuple[str | None, str | None]:
    if not snapshot_slot:
        return None, None
    current_minutes = _minutes_of_slot(snapshot_slot)
    ordered = sorted(set(projection_slots), key=_minutes_of_slot)
    lower: str | None = None
    upper: str | None = None
    for slot in ordered:
        slot_minutes = _minutes_of_slot(slot)
        if slot_minutes <= current_minutes:
            lower = slot
        if slot_minutes >= current_minutes:
            upper = slot
            break
    if lower is None and ordered:
        lower = ordered[0]
    if upper is None and ordered:
        upper = ordered[-1]
    return lower, upper


def _avg_decimal(values: list[Decimal]) -> Decimal | None:
    if not values:
        return None
    return sum(values, Decimal("0")) / Decimal(len(values))


def _blend_ratio(lower_value: Decimal | None, upper_value: Decimal | None, weight_upper: Decimal) -> Decimal | None:
    if lower_value is None and upper_value is None:
        return None
    if lower_value is None:
        return upper_value
    if upper_value is None:
        return lower_value
    return (lower_value * (Decimal("1") - weight_upper)) + (upper_value * weight_upper)


def _elapsed_trading_minutes(slot: str) -> int:
    slot_minutes = _minutes_of_slot(slot)
    elapsed = 0
    for start_time, end_time in T0_TRADING_SESSIONS:
        start_minutes = start_time.hour * 60 + start_time.minute
        end_minutes = end_time.hour * 60 + end_time.minute
        if slot_minutes <= start_minutes:
            continue
        elapsed += max(0, min(slot_minutes, end_minutes) - start_minutes)
    return elapsed


def _time_weighted_ratio(snapshot_slot: str | None, final_slot: str) -> Decimal | None:
    if not snapshot_slot:
        return None
    current_elapsed = _elapsed_trading_minutes(snapshot_slot)
    final_elapsed = _elapsed_trading_minutes(final_slot)
    if final_elapsed <= 0:
        return None
    bounded_elapsed = max(0, min(current_elapsed, final_elapsed))
    return Decimal(str(bounded_elapsed / final_elapsed))


def _history_map_for_ticker(ticker: str, trading_date: date) -> dict[date, dict[str, StockT0Snapshot]]:
    history_snapshots = list(
        StockT0Snapshot.objects.filter(ticker=ticker, trading_date__lt=trading_date).order_by("-trading_date", "snapshot_slot")
    )
    by_date: dict[date, dict[str, StockT0Snapshot]] = {}
    for snapshot in history_snapshots:
        by_date.setdefault(snapshot.trading_date, {})[snapshot.snapshot_slot] = snapshot
    return by_date


def _projection_for_snapshot(
    snapshot: StockT0Snapshot,
    config: dict[str, Any],
    history_by_date: dict[date, dict[str, StockT0Snapshot]],
    final_value: Decimal | None = None,
) -> dict | None:
    projection_slots = list(config.get("projectionSlots") or [])
    lower_slot, upper_slot = _projection_bounds_for(snapshot.snapshot_slot, projection_slots)
    if not lower_slot or not upper_slot:
        return None

    current_value = _coerce_decimal(snapshot.total_match_val)
    if current_value <= 0:
        return None

    final_slot = str(_config_value(config, "projectionFinalSlot", "15:00"))
    window20 = int(_config_value(config, "projectionWindow20", 20))
    window5 = int(_config_value(config, "projectionWindow5", 5))
    weight20 = Decimal(str(_config_value(config, "projectionWeight20", 0.6)))
    weight5 = Decimal(str(_config_value(config, "projectionWeight5", 0.4)))

    lower_ratios: list[Decimal] = []
    upper_ratios: list[Decimal] = []
    for hist_date in sorted(history_by_date.keys(), reverse=True):
        day_map = history_by_date[hist_date]
        final_snapshot = day_map.get(final_slot)
        if not final_snapshot:
            continue
        final_value = _coerce_decimal(final_snapshot.total_match_val)
        if final_value <= 0:
            continue
        lower_snapshot = day_map.get(lower_slot)
        upper_snapshot = day_map.get(upper_slot)
        if lower_snapshot and _coerce_decimal(lower_snapshot.total_match_val) > 0:
            lower_ratios.append(_coerce_decimal(lower_snapshot.total_match_val) / final_value)
        if upper_snapshot and _coerce_decimal(upper_snapshot.total_match_val) > 0:
            upper_ratios.append(_coerce_decimal(upper_snapshot.total_match_val) / final_value)

    if lower_slot == upper_slot:
        interpolation_weight = Decimal("0")
        projection_slot = lower_slot
    else:
        lower_minutes = _minutes_of_slot(lower_slot)
        upper_minutes = _minutes_of_slot(upper_slot)
        current_minutes = _minutes_of_slot(snapshot.snapshot_slot)
        span = max(1, upper_minutes - lower_minutes)
        interpolation_weight = Decimal(str((current_minutes - lower_minutes) / span))
        projection_slot = f"{lower_slot}->{upper_slot}"

    lower_ratio20 = _avg_decimal(lower_ratios[:window20])
    lower_ratio5 = _avg_decimal(lower_ratios[:window5])
    upper_ratio20 = _avg_decimal(upper_ratios[:window20])
    upper_ratio5 = _avg_decimal(upper_ratios[:window5])

    ratio20 = _blend_ratio(lower_ratio20, upper_ratio20, interpolation_weight)
    ratio5 = _blend_ratio(lower_ratio5, upper_ratio5, interpolation_weight)
    historical_weighted_ratio = ((ratio20 or ratio5 or Decimal("0")) * weight20) + ((ratio5 or ratio20 or Decimal("0")) * weight5)
    if historical_weighted_ratio <= 0:
        historical_weighted_ratio = None

    historical_projected_total_match_val = None
    historical_error_pct = None
    if historical_weighted_ratio is not None and historical_weighted_ratio > 0:
        historical_projected_total_match_val = current_value / historical_weighted_ratio
        if final_value is not None and final_value > 0:
            historical_error_pct = ((historical_projected_total_match_val - final_value) / final_value) * Decimal("100")

    time_weighted_ratio = _time_weighted_ratio(snapshot.snapshot_slot, final_slot)
    time_weighted_projected_total_match_val = None
    time_weighted_error_pct = None
    if time_weighted_ratio is not None and time_weighted_ratio > 0:
        time_weighted_projected_total_match_val = current_value / time_weighted_ratio
        if final_value is not None and final_value > 0:
            time_weighted_error_pct = ((time_weighted_projected_total_match_val - final_value) / final_value) * Decimal("100")

    ratio_method = "historical_blend" if historical_projected_total_match_val is not None else "time_weighted_fallback"
    weighted_ratio = historical_weighted_ratio or time_weighted_ratio
    projected_total_match_val = historical_projected_total_match_val or time_weighted_projected_total_match_val
    error_pct = historical_error_pct if historical_projected_total_match_val is not None else time_weighted_error_pct
    if weighted_ratio is None or projected_total_match_val is None:
        return None

    return {
        "projectionSlot": projection_slot,
        "projectionLowerSlot": lower_slot,
        "projectionUpperSlot": upper_slot,
        "projectionSourceSlot": snapshot.snapshot_slot,
        "projectionCurrentValue": current_value,
        "projectionRatioAvg20": ratio20,
        "projectionRatioAvg5": ratio5,
        "projectionWeightedRatio": weighted_ratio,
        "projectedTotalMatchVal": projected_total_match_val,
        "historicalWeightedRatio": historical_weighted_ratio,
        "historicalProjectedTotalMatchVal": historical_projected_total_match_val,
        "historicalErrorPct": historical_error_pct,
        "timeWeightedRatio": time_weighted_ratio,
        "timeWeightedProjectedTotalMatchVal": time_weighted_projected_total_match_val,
        "timeWeightedErrorPct": time_weighted_error_pct,
        "projectionSample20": min(max(len(lower_ratios), len(upper_ratios)), window20),
        "projectionSample5": min(max(len(lower_ratios), len(upper_ratios)), window5),
        "projectionFinalSlot": final_slot,
        "projectionWindow20": window20,
        "projectionWindow5": window5,
        "projectionWeight20": weight20,
        "projectionWeight5": weight5,
        "projectionInterpolationWeight": interpolation_weight,
        "projectionMethod": ratio_method,
        "projectionErrorPct": error_pct,
    }


def _build_projection(ticker: str, trading_date: date) -> dict | None:
    config = setting_services.get_t0_snapshot_schedule_config()
    current_snapshots = list(
        StockT0Snapshot.objects.filter(ticker=ticker, trading_date=trading_date).order_by("snapshot_slot")
    )
    if not current_snapshots:
        return None
    latest_snapshot = max(current_snapshots, key=lambda item: _slot_index(item.snapshot_slot))
    history_by_date = _history_map_for_ticker(ticker, trading_date)
    final_slot = str(_config_value(config, "projectionFinalSlot", "15:00"))
    final_snapshot = next((item for item in current_snapshots if item.snapshot_slot == final_slot), None)
    final_value = _coerce_decimal(final_snapshot.total_match_val) if final_snapshot else None
    return _projection_for_snapshot(latest_snapshot, config, history_by_date, final_value)


def _serialize_projection(projection: dict | None) -> dict | None:
    if not projection:
        return None
    return {
        "projectionSlot": projection.get("projectionSlot"),
        "projectionLowerSlot": projection.get("projectionLowerSlot"),
        "projectionUpperSlot": projection.get("projectionUpperSlot"),
        "projectionSourceSlot": projection.get("projectionSourceSlot"),
        "projectionCurrentValue": projection.get("projectionCurrentValue"),
        "projectionRatioAvg20": projection.get("projectionRatioAvg20"),
        "projectionRatioAvg5": projection.get("projectionRatioAvg5"),
        "projectionWeightedRatio": projection.get("projectionWeightedRatio"),
        "projectedTotalMatchVal": projection.get("projectedTotalMatchVal"),
        "historicalWeightedRatio": projection.get("historicalWeightedRatio"),
        "historicalProjectedTotalMatchVal": projection.get("historicalProjectedTotalMatchVal"),
        "historicalErrorPct": projection.get("historicalErrorPct"),
        "timeWeightedRatio": projection.get("timeWeightedRatio"),
        "timeWeightedProjectedTotalMatchVal": projection.get("timeWeightedProjectedTotalMatchVal"),
        "timeWeightedErrorPct": projection.get("timeWeightedErrorPct"),
        "projectionSample20": projection.get("projectionSample20"),
        "projectionSample5": projection.get("projectionSample5"),
        "projectionFinalSlot": projection.get("projectionFinalSlot"),
        "projectionWindow20": projection.get("projectionWindow20"),
        "projectionWindow5": projection.get("projectionWindow5"),
        "projectionWeight20": projection.get("projectionWeight20"),
        "projectionWeight5": projection.get("projectionWeight5"),
        "projectionInterpolationWeight": projection.get("projectionInterpolationWeight"),
        "projectionMethod": projection.get("projectionMethod"),
        "projectionErrorPct": projection.get("projectionErrorPct"),
    }


def upsert_realtime_state(ticker: str, payload: dict[str, Any], trading_date: date | None = None) -> dict:
    _ensure_t0_tables()
    normalized_ticker = (ticker or "").strip().upper()
    if not _valid_ticker(normalized_ticker):
        raise BadRequestError("Ticker is invalid for T0 realtime state")
    total_match_vol, total_match_val = _extract_trade_totals(payload)
    now = timezone.now()
    entity, _ = StockT0RealtimeState.objects.update_or_create(
        ticker=normalized_ticker,
        defaults={
            "trading_date": trading_date or _today_vn(),
            "last_message_at": now,
            "total_match_vol": total_match_vol,
            "total_match_val": total_match_val,
            "raw_payload": json.dumps(payload, ensure_ascii=False),
            "updated_at": now,
            "created_at": now,
        },
    )
    return _serialize_realtime(entity)


def purge_stale_foreign_states(trading_date: date | None = None) -> int:
    _ensure_t0_tables()
    today = trading_date or _today_vn()
    deleted_count, _ = StockT0ForeignState.objects.exclude(trading_date=today).delete()
    return int(deleted_count or 0)


def replace_foreign_state_rows(rows: dict[str, dict[str, Any]], trading_date: date | None = None) -> dict:
    _ensure_t0_tables()
    today = trading_date or _today_vn()
    now = timezone.now()
    purge_stale_foreign_states(today)
    valid_tickers = [ticker.strip().upper() for ticker in rows.keys() if _valid_ticker(ticker)]
    if valid_tickers:
        StockT0ForeignState.objects.filter(trading_date=today).exclude(ticker__in=valid_tickers).delete()
    for ticker, row in rows.items():
        normalized_ticker = (ticker or "").strip().upper()
        if not _valid_ticker(normalized_ticker):
            continue
        StockT0ForeignState.objects.update_or_create(
            ticker=normalized_ticker,
            trading_date=today,
            defaults={
                "source_exchange": row.get("sourceExchange"),
                "buy_foreign_qtty": int(row.get("foreignBuyVolTotal") or 0),
                "sell_foreign_qtty": int(row.get("foreignSellVolTotal") or 0),
                "buy_foreign_value": _coerce_decimal(row.get("foreignBuyValTotal")),
                "sell_foreign_value": _coerce_decimal(row.get("foreignSellValTotal")),
                "fetched_at": now,
                "raw_payload": json.dumps(row.get("rawPayload") or {}, ensure_ascii=False),
                "updated_at": now,
                "created_at": now,
            },
        )
    return {
        "tradingDate": today.isoformat(),
        "count": len(rows),
        "fetchedAt": now.isoformat(),
    }


def get_foreign_state_map(trading_date: date | None = None) -> dict[str, dict]:
    _ensure_t0_tables()
    today = trading_date or _today_vn()
    states = StockT0ForeignState.objects.filter(trading_date=today).order_by("ticker")
    return {item.ticker.upper(): _serialize_foreign_state(item) for item in states}


def snapshot_due_realtime_states(
    snapshot_slot: str,
    snapshot_time: datetime | None = None,
    trading_date: date | None = None,
    foreign_payloads: dict[str, dict] | None = None,
) -> dict:
    _ensure_t0_tables()
    now = snapshot_time or timezone.now()
    today = trading_date or _today_vn()
    states = list(StockT0RealtimeState.objects.filter(trading_date=today).order_by("ticker"))
    count = 0
    foreign_state_map = foreign_payloads or get_foreign_state_map(today)
    for state in states:
        foreign_payload = foreign_state_map.get(state.ticker.upper(), {})
        StockT0Snapshot.objects.update_or_create(
            ticker=state.ticker,
            trading_date=today,
            snapshot_slot=snapshot_slot,
            defaults={
                "snapshot_at": now,
                "total_match_vol": state.total_match_vol,
                "total_match_val": state.total_match_val,
                "foreign_buy_vol_total": foreign_payload.get("foreignBuyVolTotal"),
                "foreign_sell_vol_total": foreign_payload.get("foreignSellVolTotal"),
                "foreign_buy_val_total": foreign_payload.get("foreignBuyValTotal"),
                "foreign_sell_val_total": foreign_payload.get("foreignSellValTotal"),
                "net_foreign_vol": foreign_payload.get("netForeignVol"),
                "net_foreign_val": foreign_payload.get("netForeignVal"),
                "foreign_data_source": foreign_payload.get("foreignDataSource"),
                "raw_payload": state.raw_payload,
                "updated_at": now,
                "created_at": now,
            },
        )
        count += 1
    setting_services.save_t0_worker_status(
        {
            "lastSnapshotAt": now.isoformat(),
            "lastSnapshotSlot": snapshot_slot,
            "lastSnapshotCount": count,
        }
    )
    return {
        "snapshotSlot": snapshot_slot,
        "snapshotAt": now.isoformat(),
        "tradingDate": today.isoformat(),
        "count": count,
    }


def list_t0_snapshots(page: int, size: int, ticker: str | None, trading_date: date | None) -> dict:
    _ensure_t0_tables()
    if page < 0:
        raise BadRequestError("Page must be >= 0")
    if size <= 0 or size > 200:
        raise BadRequestError("Size must be between 1 and 200")
    qs = StockT0Snapshot.objects.order_by("-trading_date", "ticker", "snapshot_slot")
    normalized_ticker = (ticker or "").strip().upper()
    if normalized_ticker:
        qs = qs.filter(ticker=normalized_ticker)
    if trading_date is not None:
        qs = qs.filter(trading_date=trading_date)
    paginator = Paginator(qs, size)
    current = paginator.get_page(page + 1)
    return {
        "items": [_serialize_snapshot(item) for item in current.object_list],
        "page": page,
        "size": size,
        "totalElements": paginator.count,
        "totalPages": paginator.num_pages,
    }


def list_t0_snapshot_groups(page: int, size: int, ticker: str | None, trading_date: date | None) -> dict:
    _ensure_t0_tables()
    if page < 0:
        raise BadRequestError("Page must be >= 0")
    if size <= 0 or size > 200:
        raise BadRequestError("Size must be between 1 and 200")
    qs = StockT0Snapshot.objects.all()
    normalized_ticker = (ticker or "").strip().upper()
    if normalized_ticker:
        qs = qs.filter(ticker=normalized_ticker)
    if trading_date is not None:
        qs = qs.filter(trading_date=trading_date)

    grouped = list(
        qs.values("ticker", "trading_date")
        .annotate(snapshot_count=Count("id"))
        .order_by("-trading_date", "ticker")
    )
    paginator = Paginator(grouped, size)
    current = paginator.get_page(page + 1)

    items: list[dict] = []
    for row in current.object_list:
        latest = (
            StockT0Snapshot.objects.filter(ticker=row["ticker"], trading_date=row["trading_date"])
            .order_by("-snapshot_slot")
            .first()
        )
        projection = _serialize_projection(_build_projection(row["ticker"], row["trading_date"]))
        items.append(
            {
                "ticker": row["ticker"],
                "tradingDate": row["trading_date"].isoformat() if hasattr(row["trading_date"], "isoformat") else str(row["trading_date"]),
                "snapshotCount": int(row["snapshot_count"] or 0),
                "latestSlot": latest.snapshot_slot if latest else None,
                "latestSnapshotAt": latest.snapshot_at.isoformat() if latest and latest.snapshot_at else None,
                "latestTotalMatchVol": int(latest.total_match_vol or 0) if latest else 0,
                "latestTotalMatchVal": latest.total_match_val if latest else None,
                "latestForeignNetVol": int(latest.net_foreign_vol or 0) if latest else 0,
                "latestForeignNetVal": latest.net_foreign_val if latest else None,
                "hasRawPayload": bool((latest.raw_payload or "").strip()) if latest else False,
                "projection": projection,
            }
        )

    return {
        "items": items,
        "page": page,
        "size": size,
        "totalElements": paginator.count,
        "totalPages": paginator.num_pages,
    }


def list_t0_realtime_groups(page: int, size: int, ticker: str | None, trading_date: date | None) -> dict:
    _ensure_t0_tables()
    if page < 0:
        raise BadRequestError("Page must be >= 0")
    if size <= 0 or size > 200:
        raise BadRequestError("Size must be between 1 and 200")
    target_date = trading_date or _today_vn()
    qs = StockT0RealtimeState.objects.filter(trading_date=target_date).order_by("ticker")
    normalized_ticker = (ticker or "").strip().upper()
    if normalized_ticker:
        qs = qs.filter(ticker=normalized_ticker)
    foreign_map = get_foreign_state_map(target_date)
    paginator = Paginator(qs, size)
    current = paginator.get_page(page + 1)

    items: list[dict] = []
    for row in current.object_list:
        foreign = foreign_map.get(row.ticker.upper(), {})
        items.append(
            {
                "ticker": row.ticker,
                "tradingDate": target_date.isoformat(),
                "snapshotCount": 1,
                "latestSlot": "RT",
                "latestSnapshotAt": row.last_message_at.isoformat() if row.last_message_at else None,
                "latestTotalMatchVol": int(row.total_match_vol or 0),
                "latestTotalMatchVal": row.total_match_val,
                "latestForeignNetVol": int(foreign.get("netForeignVol") or 0),
                "latestForeignNetVal": foreign.get("netForeignVal"),
                "hasRawPayload": bool((row.raw_payload or "").strip()),
                "projection": None,
            }
        )

    return {
        "items": items,
        "page": page,
        "size": size,
        "totalElements": paginator.count,
        "totalPages": paginator.num_pages,
    }


def get_t0_ticker_timeline(ticker: str, trading_date: date | None) -> dict:
    _ensure_t0_tables()
    normalized_ticker = (ticker or "").strip().upper()
    if not _valid_ticker(normalized_ticker):
        raise BadRequestError("Ticker is required")
    target_date = trading_date or _today_vn()
    snapshots = list(
        StockT0Snapshot.objects.filter(ticker=normalized_ticker, trading_date=target_date).order_by("snapshot_slot")
    )
    config = setting_services.get_t0_snapshot_schedule_config()
    history_by_date = _history_map_for_ticker(normalized_ticker, target_date)
    final_slot = str(_config_value(config, "projectionFinalSlot", "15:00"))
    final_snapshot = next((item for item in snapshots if item.snapshot_slot == final_slot), None)
    final_value = _coerce_decimal(final_snapshot.total_match_val) if final_snapshot else None
    return {
        "ticker": normalized_ticker,
        "tradingDate": target_date.isoformat(),
        "timeline": [
            {
                **_serialize_snapshot(item),
                "projection": _serialize_projection(_projection_for_snapshot(item, config, history_by_date, final_value)),
            }
            for item in snapshots
        ],
        "projection": _serialize_projection(_build_projection(normalized_ticker, target_date)),
    }


def get_t0_status() -> dict:
    _ensure_t0_tables()
    return setting_services.get_t0_worker_status()


def get_existing_snapshot_slots(trading_date: date) -> set[str]:
    _ensure_t0_tables()
    return set(StockT0Snapshot.objects.filter(trading_date=trading_date).values_list("snapshot_slot", flat=True).distinct())


def _owner_payload(owner_id: str, expires_at: datetime) -> dict:
    return {
        "ownerId": owner_id,
        "pid": os.getpid(),
        "host": socket.gethostname(),
        "expiresAt": expires_at.isoformat(),
        "heartbeatAt": timezone.now().isoformat(),
    }


@transaction.atomic
def acquire_worker_lock(owner_id: str) -> None:
    setting_services._ensure_app_settings_table()
    expires_at = timezone.now() + timedelta(seconds=T0_LOCK_TTL_SECONDS)
    entity = AppSetting.objects.select_for_update().filter(setting_key=setting_services.APP_SETTING_T0_WORKER_LOCK).first()
    if entity and (entity.setting_value or "").strip():
        try:
            current = json.loads(entity.setting_value)
        except json.JSONDecodeError:
            current = {}
        current_owner = str(current.get("ownerId") or "")
        current_expires = current.get("expiresAt")
        if current_owner and current_owner != owner_id and current_expires:
            try:
                parsed_expires = datetime.fromisoformat(current_expires)
                if timezone.is_naive(parsed_expires):
                    parsed_expires = timezone.make_aware(parsed_expires, timezone.get_current_timezone())
                if parsed_expires > timezone.now():
                    raise BadRequestError(f"T0 worker is already running on {current.get('host') or 'another host'}")
            except ValueError:
                pass
    setting_services.save_t0_worker_lock(_owner_payload(owner_id, expires_at))


def refresh_worker_lock(owner_id: str) -> None:
    expires_at = timezone.now() + timedelta(seconds=T0_LOCK_TTL_SECONDS)
    current = setting_services.get_t0_worker_lock()
    if str(current.get("ownerId") or "") not in ("", owner_id):
        raise BadRequestError("T0 worker lock has been taken by another instance")
    setting_services.save_t0_worker_lock(_owner_payload(owner_id, expires_at))


def release_worker_lock(owner_id: str) -> None:
    current = setting_services.get_t0_worker_lock()
    if str(current.get("ownerId") or "") == owner_id:
        setting_services.save_t0_worker_lock({})


def _auth_message(api_key: str, api_secret: str) -> bytes:
    timestamp = int(time.time())
    nonce = str(int(time.time() * 1_000_000))
    message = f"{api_key}:{timestamp}:{nonce}"
    signature = hmac.new(api_secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()
    return msgpack.packb(
        {
            "action": "auth",
            "api_key": api_key,
            "signature": signature,
            "timestamp": timestamp,
            "nonce": nonce,
        }
    )


def _subscribe_message(tickers: list[str]) -> bytes:
    return msgpack.packb(
        {
            "action": "subscribe",
            "channels": [
                {
                    "name": "tick.G1.msgpack",
                    "symbols": tickers,
                }
            ],
        }
    )


def _decode_message(raw: bytes | str) -> dict[str, Any]:
    if isinstance(raw, str):
        return json.loads(raw)
    return msgpack.unpackb(raw, raw=False)


def _slot_due(now_vn: datetime, slot: str, captured_slots: set[str]) -> bool:
    if slot in captured_slots:
        return False
    slot_time = datetime.combine(now_vn.date(), _parse_slot(slot), tzinfo=T0_TIMEZONE)
    delta_seconds = (now_vn - slot_time).total_seconds()
    return 0 <= delta_seconds <= T0_SNAPSHOT_GRACE_SECONDS


@dataclass
class WorkerConfig:
    api_key: str
    api_secret: str
    enabled: bool
    times: list[str]


def load_worker_config() -> WorkerConfig:
    dnse = setting_services.get_dnse_entity()
    schedule = setting_services.get_t0_snapshot_schedule_config()
    return WorkerConfig(
        api_key=(dnse.api_key or "").strip(),
        api_secret=(dnse.api_secret or "").strip(),
        enabled=bool(schedule.get("enabled", False)),
        times=list(schedule.get("times") or T0_DEFAULT_TIMES),
    )


class DnseT0Worker:
    def __init__(self) -> None:
        self.owner_id = str(uuid.uuid4())
        self.backoff_seconds = 1
        self.last_heartbeat_at = 0.0
        self.captured_slots: set[str] = set()
        self.current_trading_date = _today_vn()
        self.websocket = None
        self.subscribed_tickers: list[str] = []
        self.last_message_at: str | None = None
        self.connection_started_at: str | None = None
        self.connection_started_monotonic: float | None = None
        self.last_auth_success_at: str | None = None
        self.last_reconnect_at: str | None = None
        self.dnse_key_masked: str | None = None
        self.reconnect_count = 0

    async def run_forever(self) -> None:
        await _run_sync(_ensure_t0_tables)
        await _run_sync(acquire_worker_lock, self.owner_id)
        await _run_sync(
            setting_services.save_t0_worker_status,
            {
                "running": True,
                "connected": False,
                "phase": "Starting",
                "lastError": None,
            }
        )
        try:
            while True:
                await self._run_once()
                self.backoff_seconds = 1
        except asyncio.CancelledError:
            raise
        except Exception as ex:
            logger.exception("T0 worker stopped with fatal error")
            await _run_sync(
                setting_services.save_t0_worker_status,
                {
                    "running": False,
                    "connected": False,
                    "phase": "Failed",
                    "lastError": str(ex),
                }
            )
            raise
        finally:
            await self._disconnect()
            await _run_sync(release_worker_lock, self.owner_id)
            await _run_sync(
                setting_services.save_t0_worker_status,
                {
                    "running": False,
                    "connected": False,
                    "phase": "Stopped",
                }
            )

    async def _run_once(self) -> None:
        config = await _run_sync(load_worker_config)
        self.dnse_key_masked = _mask_api_key(config.api_key)
        tickers = await _run_sync(list_valid_t0_tickers)
        self._roll_trading_day_if_needed()
        await self._prime_captured_slots(self.current_trading_date)

        if not config.enabled:
            await _run_sync(
                setting_services.save_t0_worker_status,
                {
                    "connected": False,
                    "phase": "Disabled",
                    "subscribedCount": 0,
                    "subscribedTickers": len(tickers),
                    "dnseKeyMasked": self.dnse_key_masked,
                }
            )
            await self._sleep_with_heartbeat(15)
            return
        if not config.api_key or not config.api_secret:
            await _run_sync(
                setting_services.save_t0_worker_status,
                {
                    "connected": False,
                    "phase": "Missing DNSE credentials",
                    "subscribedCount": 0,
                    "subscribedTickers": len(tickers),
                    "dnseKeyMasked": self.dnse_key_masked,
                }
            )
            await self._sleep_with_heartbeat(15)
            return
        if not tickers:
            await _run_sync(
                setting_services.save_t0_worker_status,
                {
                    "connected": False,
                    "phase": "No valid tickers",
                    "subscribedCount": 0,
                    "subscribedTickers": 0,
                    "dnseKeyMasked": self.dnse_key_masked,
                }
            )
            await self._sleep_with_heartbeat(30)
            return

        try:
            await self._connect_and_stream(config, tickers)
        except Exception as ex:
            is_proactive_reconnect = "Proactive reconnect after 7h45" in str(ex)
            logger.warning("T0 worker reconnecting after error: %s", ex)
            await _run_sync(
                setting_services.save_t0_worker_status,
                {
                    "connected": False,
                    "phase": "Proactive reconnect after 7h45" if is_proactive_reconnect else f"Reconnecting in {self.backoff_seconds}s",
                    "lastError": None if is_proactive_reconnect else str(ex),
                    "subscribedCount": len(self.subscribed_tickers),
                    "subscribedTickers": len(tickers),
                    "dnseKeyMasked": self.dnse_key_masked,
                    "connectionStartedAt": self.connection_started_at,
                    "authSuccessAt": self.last_auth_success_at,
                    "lastReconnectAt": self.last_reconnect_at,
                    "reconnectCount": self.reconnect_count,
                }
            )
            await self._disconnect()
            await self._sleep_with_heartbeat(self.backoff_seconds)
            self.backoff_seconds = min(self.backoff_seconds * 2, 60)

    async def _connect_and_stream(self, config: WorkerConfig, tickers: list[str]) -> None:
        url = f"{DNSE_WS_URL}/v1/stream?encoding=msgpack"
        self.subscribed_tickers = tickers
        await _run_sync(
            setting_services.save_t0_worker_status,
            {
                "connected": False,
                "phase": "Connecting",
                "subscribedTickers": len(tickers),
                "subscribedCount": 0,
                "lastError": None,
                "dnseKeyMasked": self.dnse_key_masked,
            }
        )
        self.websocket = await websockets.connect(url, ping_interval=30, ping_timeout=30, max_queue=None)
        welcome = _decode_message(await self.websocket.recv())
        logger.info("T0 worker connected with session %s", welcome.get("session_id") or welcome.get("sid"))
        await self.websocket.send(_auth_message(config.api_key, config.api_secret))
        auth_response = _decode_message(await self.websocket.recv())
        if (auth_response.get("action") or auth_response.get("a")) != "auth_success":
            raise BadRequestError(auth_response.get("message") or auth_response.get("msg") or "DNSE auth failed")
        now_iso = timezone.now().isoformat()
        if self.connection_started_at is not None:
            self.reconnect_count += 1
        self.connection_started_at = now_iso
        self.connection_started_monotonic = time.monotonic()
        self.last_auth_success_at = now_iso
        self.last_reconnect_at = now_iso
        await self.websocket.send(_subscribe_message(tickers))
        await _run_sync(
            setting_services.save_t0_worker_status,
            {
                "connected": True,
                "phase": "Streaming",
                "subscribedCount": len(tickers),
                "subscribedTickers": len(tickers),
                "lastError": None,
                "dnseKeyMasked": self.dnse_key_masked,
                "connectionStartedAt": self.connection_started_at,
                "authSuccessAt": self.last_auth_success_at,
                "lastReconnectAt": self.last_reconnect_at,
                "reconnectCount": self.reconnect_count,
            }
        )

        while True:
            try:
                raw_message = await asyncio.wait_for(self.websocket.recv(), timeout=1)
                data = _decode_message(raw_message)
                await self._handle_message(data)
            except asyncio.TimeoutError:
                if self._should_proactive_reconnect():
                    raise BadRequestError("Proactive reconnect after 7h45")
                await self._handle_due_snapshots(config.times)
                await self._heartbeat_status()

    async def _handle_message(self, data: dict[str, Any]) -> None:
        action = data.get("action") or data.get("a")
        if action == "ping":
            await self.websocket.send(msgpack.packb({"action": "pong"}))
            return
        if action == "error":
            raise BadRequestError(data.get("message") or data.get("msg") or "DNSE websocket error")
        if data.get("T") not in ("t", "te"):
            return
        ticker = str(data.get("s") or data.get("symbol") or data.get("Symbol") or "").strip().upper()
        if not _valid_ticker(ticker):
            return
        await _run_sync(upsert_realtime_state, ticker, data, self.current_trading_date)
        self.last_message_at = timezone.now().isoformat()
        await _run_sync(setting_services.save_t0_worker_status, {"lastMessageAt": self.last_message_at})
        await self._handle_due_snapshots((await _run_sync(load_worker_config)).times)

    async def _handle_due_snapshots(self, slots: list[str]) -> None:
        self._roll_trading_day_if_needed()
        now_vn = _now_vn()
        for slot in slots:
            if not _slot_due(now_vn, slot, self.captured_slots):
                continue
            await _run_sync(setting_services.save_t0_worker_status, {"phase": f"Snapshot {slot} started"})
            foreign_payloads = await _run_sync(get_foreign_state_map, self.current_trading_date)
            await _run_sync(snapshot_due_realtime_states, slot, timezone.now(), self.current_trading_date, foreign_payloads)
            self.captured_slots.add(slot)
            await _run_sync(setting_services.save_t0_worker_status, {"phase": f"Snapshot {slot} done"})

    def _roll_trading_day_if_needed(self) -> None:
        today = _today_vn()
        if today == self.current_trading_date:
            return
        self.current_trading_date = today
        self.captured_slots = set()

    async def _prime_captured_slots(self, trading_date: date) -> None:
        existing_slots = await _run_sync(get_existing_snapshot_slots, trading_date)
        if existing_slots:
            self.captured_slots.update(existing_slots)

    async def _heartbeat_status(self) -> None:
        now_monotonic = time.monotonic()
        if now_monotonic - self.last_heartbeat_at < 15:
            return
        await _run_sync(refresh_worker_lock, self.owner_id)
        await _run_sync(
            setting_services.save_t0_worker_status,
            {
                "running": True,
                "connected": self.websocket is not None and not getattr(self.websocket, "closed", False),
                "phase": "Streaming",
                "subscribedCount": len(self.subscribed_tickers),
                "subscribedTickers": len(self.subscribed_tickers),
                "lastMessageAt": self.last_message_at,
                "dnseKeyMasked": self.dnse_key_masked,
                "connectionStartedAt": self.connection_started_at,
                "authSuccessAt": self.last_auth_success_at,
                "lastReconnectAt": self.last_reconnect_at,
                "reconnectCount": self.reconnect_count,
            }
        )
        self.last_heartbeat_at = now_monotonic

    def _should_proactive_reconnect(self) -> bool:
        if self.connection_started_monotonic is None:
            return False
        return (time.monotonic() - self.connection_started_monotonic) >= T0_PROACTIVE_RECONNECT_SECONDS

    async def _sleep_with_heartbeat(self, seconds: int) -> None:
        end_at = time.monotonic() + seconds
        while time.monotonic() < end_at:
            await _run_sync(refresh_worker_lock, self.owner_id)
            await asyncio.sleep(min(5, max(1, end_at - time.monotonic())))

    async def _disconnect(self) -> None:
        if self.websocket is not None:
            try:
                await self.websocket.close()
            except Exception:
                pass
        self.websocket = None
        self.subscribed_tickers = []
        self.connection_started_monotonic = None
