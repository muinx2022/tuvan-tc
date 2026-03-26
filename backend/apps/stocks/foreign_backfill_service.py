from __future__ import annotations

import json
import logging
import os
import socket
import time
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from django.db import transaction
from django.utils import timezone

from apps.settings_app.models import AppSetting
from apps.settings_app import services as setting_services
from apps.stocks.models import StockHistory
from apps.stocks.ssi_history_client import SsiHistoryClient
from apps.stocks.ssi_history_parser import parse_history_payload
from common.exceptions import BadRequestError

logger = logging.getLogger(__name__)

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
FOREIGN_BACKFILL_START_HOUR = 5
FOREIGN_BACKFILL_INTERVAL_SECONDS = 60 * 60
FOREIGN_BACKFILL_LOCK_TTL_SECONDS = 90


def _today_vn() -> date:
    return timezone.now().astimezone(VN_TZ).date()


def _now_vn() -> datetime:
    return timezone.now().astimezone(VN_TZ)


def _target_trading_date(now_vn: datetime | None = None) -> date:
    base = now_vn or _now_vn()
    return base.date() - timedelta(days=1)


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
    expires_at = timezone.now() + timedelta(seconds=FOREIGN_BACKFILL_LOCK_TTL_SECONDS)
    entity = AppSetting.objects.select_for_update().filter(setting_key=setting_services.APP_SETTING_FOREIGN_BACKFILL_LOCK).first()
    if entity and (entity.setting_value or "").strip():
        try:
            current = json.loads(entity.setting_value)
        except json.JSONDecodeError:
            current = {}
        current_owner = str(current.get("ownerId") or "")
        current_expires = current.get("expiresAt")
        if current_owner and current_owner != owner_id and current_expires:
            parsed_expires = datetime.fromisoformat(current_expires)
            if timezone.is_naive(parsed_expires):
                parsed_expires = timezone.make_aware(parsed_expires, timezone.get_current_timezone())
            if parsed_expires > timezone.now():
                raise BadRequestError(f"Foreign backfill worker is already running on {current.get('host') or 'another host'}")
    setting_services.save_foreign_backfill_lock(_owner_payload(owner_id, expires_at))


def refresh_worker_lock(owner_id: str) -> None:
    expires_at = timezone.now() + timedelta(seconds=FOREIGN_BACKFILL_LOCK_TTL_SECONDS)
    current = setting_services.get_foreign_backfill_lock()
    if str(current.get("ownerId") or "") not in ("", owner_id):
        raise BadRequestError("Foreign backfill lock has been taken by another instance")
    setting_services.save_foreign_backfill_lock(_owner_payload(owner_id, expires_at))


def release_worker_lock(owner_id: str) -> None:
    current = setting_services.get_foreign_backfill_lock()
    if str(current.get("ownerId") or "") == owner_id:
        setting_services.save_foreign_backfill_lock({})


def _should_start_for_day(now_vn: datetime, runtime: dict) -> bool:
    if now_vn.hour < FOREIGN_BACKFILL_START_HOUR:
        return False
    target_date = _target_trading_date(now_vn).isoformat()
    if runtime.get("completedDate") == target_date:
        return False
    last_attempt_at = runtime.get("lastAttemptAt")
    if runtime.get("targetDate") == target_date and last_attempt_at:
        try:
            parsed = datetime.fromisoformat(last_attempt_at)
            if timezone.is_naive(parsed):
                parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
            if (timezone.now() - parsed).total_seconds() < FOREIGN_BACKFILL_INTERVAL_SECONDS:
                return False
        except ValueError:
            pass
    return True


def _fetch_foreign_history_row(http: SsiHistoryClient, ticker: str, target_date: date):
    payload = http.fetch_histories(ticker, target_date, 5, page=1)
    parsed = parse_history_payload(payload, ticker, None)
    for history in parsed.histories:
        if history.trading_date == target_date:
            return history
    return None


def backfill_foreign_for_date(target_date: date) -> dict:
    tickers = list(
        StockHistory.objects.filter(trading_date=target_date).order_by("ticker").values_list("ticker", flat=True).distinct()
    )
    http = SsiHistoryClient()
    updated = 0
    failed = 0
    for ticker in tickers:
        try:
            fresh = _fetch_foreign_history_row(http, str(ticker).strip().upper(), target_date)
            if fresh is None:
                continue
            StockHistory.objects.filter(ticker=fresh.ticker, trading_date=target_date).update(
                open_price=fresh.open_price,
                high_price=fresh.high_price,
                low_price=fresh.low_price,
                close_price=fresh.close_price,
                volume=fresh.volume,
                avg_price=fresh.avg_price,
                price_changed=fresh.price_changed,
                per_price_change=fresh.per_price_change,
                total_match_vol=fresh.total_match_vol,
                total_match_val=fresh.total_match_val,
                foreign_buy_vol_total=fresh.foreign_buy_vol_total,
                foreign_sell_vol_total=fresh.foreign_sell_vol_total,
                raw_payload=fresh.raw_payload,
            )
            updated += 1
        except Exception as ex:
            failed += 1
            logger.warning("Foreign backfill failed for %s on %s: %s", ticker, target_date.isoformat(), ex)
    quality = evaluate_foreign_quality(target_date)
    return {
        "targetDate": target_date.isoformat(),
        "updatedTickers": updated,
        "failedTickers": failed,
        "quality": quality,
    }


def evaluate_foreign_quality(target_date: date) -> dict:
    rows = list(
        StockHistory.objects.filter(trading_date=target_date).order_by("-total_match_val", "ticker")
    )
    total_rows = len(rows)
    rows_with_fields = 0
    positive_rows = 0
    zero_rows = 0
    missing_rows = 0
    for row in rows:
        buy = row.foreign_buy_vol_total
        sell = row.foreign_sell_vol_total
        if buy is None and sell is None:
            missing_rows += 1
            continue
        rows_with_fields += 1
        if int(buy or 0) > 0 or int(sell or 0) > 0:
            positive_rows += 1
        else:
            zero_rows += 1

    top_rows = rows[:50]
    top_non_missing = 0
    top_positive = 0
    top_zero = 0
    for row in top_rows:
        buy = row.foreign_buy_vol_total
        sell = row.foreign_sell_vol_total
        if buy is None and sell is None:
            continue
        top_non_missing += 1
        if int(buy or 0) > 0 or int(sell or 0) > 0:
            top_positive += 1
        else:
            top_zero += 1

    is_complete = (
        total_rows > 0
        and top_positive >= max(8, min(20, max(1, len(top_rows) // 4)))
        and positive_rows >= max(20, total_rows // 20)
    )
    return {
        "targetDate": target_date.isoformat(),
        "totalRows": total_rows,
        "rowsWithFields": rows_with_fields,
        "positiveRows": positive_rows,
        "zeroRows": zero_rows,
        "missingRows": missing_rows,
        "topRows": len(top_rows),
        "topNonMissingRows": top_non_missing,
        "topPositiveRows": top_positive,
        "topZeroRows": top_zero,
        "isComplete": is_complete,
    }


@dataclass
class ForeignBackfillWorker:
    owner_id: str = ""

    def __post_init__(self) -> None:
        self.owner_id = self.owner_id or str(uuid.uuid4())

    def run_forever(self) -> None:
        acquire_worker_lock(self.owner_id)
        setting_services.save_foreign_backfill_runtime(
            {
                "running": True,
                "phase": "Starting",
                "lastError": None,
            }
        )
        try:
            while True:
                refresh_worker_lock(self.owner_id)
                self._tick()
                time.sleep(30)
        except Exception as ex:
            logger.exception("Foreign backfill worker stopped with fatal error")
            setting_services.save_foreign_backfill_runtime(
                {
                    "running": False,
                    "phase": "Failed",
                    "lastError": str(ex),
                }
            )
            raise
        finally:
            release_worker_lock(self.owner_id)
            setting_services.save_foreign_backfill_runtime(
                {
                    "running": False,
                    "phase": "Stopped",
                }
            )

    def _tick(self) -> None:
        now_vn = _now_vn()
        runtime = setting_services.get_foreign_backfill_runtime()
        target_date = _target_trading_date(now_vn)
        if not _should_start_for_day(now_vn, runtime):
            if now_vn.hour < FOREIGN_BACKFILL_START_HOUR:
                setting_services.save_foreign_backfill_runtime(
                    {
                        "phase": f"Waiting until {FOREIGN_BACKFILL_START_HOUR:02d}:00",
                        "targetDate": target_date.isoformat(),
                    }
                )
            elif runtime.get("completedDate") == target_date.isoformat():
                setting_services.save_foreign_backfill_runtime(
                    {
                        "phase": "Completed for yesterday",
                        "targetDate": target_date.isoformat(),
                    }
                )
            return

        setting_services.save_foreign_backfill_runtime(
            {
                "phase": f"Backfilling foreign data for {target_date.isoformat()}",
                "targetDate": target_date.isoformat(),
                "lastAttemptAt": timezone.now().isoformat(),
                "lastError": None,
            }
        )
        result = backfill_foreign_for_date(target_date)
        quality = result["quality"]
        payload = {
            "phase": "Completed" if quality["isComplete"] else "Will retry next hour",
            "targetDate": target_date.isoformat(),
            "lastResult": result,
            "lastQuality": quality,
            "lastCompletedAt": timezone.now().isoformat() if quality["isComplete"] else runtime.get("lastCompletedAt"),
            "completedDate": target_date.isoformat() if quality["isComplete"] else runtime.get("completedDate"),
        }
        setting_services.save_foreign_backfill_runtime(payload)
