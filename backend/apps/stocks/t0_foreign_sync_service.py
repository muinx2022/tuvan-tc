from __future__ import annotations

import json
import logging
import os
import socket
import time
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time as dt_time, timedelta
from zoneinfo import ZoneInfo

from django.db import transaction
from django.utils import timezone

from apps.settings_app.models import AppSetting
from apps.settings_app import services as setting_services
from apps.stocks.ssi_board_foreign_service import fetch_foreign_board_snapshots
from apps.stocks.t0_snapshot_service import purge_stale_foreign_states, replace_foreign_state_rows
from common.exceptions import BadRequestError

logger = logging.getLogger(__name__)

T0_FOREIGN_WORKER_LOCK_TTL_SECONDS = 90
VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def _today_vn() -> date:
    return timezone.now().astimezone(VN_TZ).date()


def _now_vn() -> datetime:
    return timezone.now().astimezone(VN_TZ)


def _parse_hhmm(value: str) -> dt_time:
    hour, minute = value.split(":")
    return dt_time(hour=int(hour), minute=int(minute))


def _window_bounds(now_vn: datetime, start_time: str, end_time: str) -> tuple[datetime, datetime]:
    start_dt = datetime.combine(now_vn.date(), _parse_hhmm(start_time), tzinfo=VN_TZ)
    end_dt = datetime.combine(now_vn.date(), _parse_hhmm(end_time), tzinfo=VN_TZ)
    return start_dt, end_dt


def _compute_next_sync_at(
    now_vn: datetime,
    start_time: str,
    end_time: str,
    refresh_minutes: int,
    last_synced_at: datetime | None = None,
) -> datetime:
    start_dt, end_dt = _window_bounds(now_vn, start_time, end_time)
    interval = timedelta(minutes=refresh_minutes)
    if now_vn < start_dt:
        return start_dt
    if now_vn > end_dt:
        return start_dt + timedelta(days=1)
    if last_synced_at is None:
        return now_vn
    candidate = last_synced_at + interval
    if candidate <= end_dt:
        return candidate
    return start_dt + timedelta(days=1)


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
    expires_at = timezone.now() + timedelta(seconds=T0_FOREIGN_WORKER_LOCK_TTL_SECONDS)
    entity = AppSetting.objects.select_for_update().filter(setting_key=setting_services.APP_SETTING_T0_FOREIGN_WORKER_LOCK).first()
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
                raise BadRequestError(f"T0 foreign worker is already running on {current.get('host') or 'another host'}")
    setting_services.save_t0_foreign_worker_lock(_owner_payload(owner_id, expires_at))


def refresh_worker_lock(owner_id: str) -> None:
    expires_at = timezone.now() + timedelta(seconds=T0_FOREIGN_WORKER_LOCK_TTL_SECONDS)
    current = setting_services.get_t0_foreign_worker_lock()
    if str(current.get("ownerId") or "") not in ("", owner_id):
        raise BadRequestError("T0 foreign worker lock has been taken by another instance")
    setting_services.save_t0_foreign_worker_lock(_owner_payload(owner_id, expires_at))


def release_worker_lock(owner_id: str) -> None:
    current = setting_services.get_t0_foreign_worker_lock()
    if str(current.get("ownerId") or "") == owner_id:
        setting_services.save_t0_foreign_worker_lock({})


@dataclass
class T0ForeignSyncWorker:
    owner_id: str = ""

    def __post_init__(self) -> None:
        self.owner_id = self.owner_id or str(uuid.uuid4())
        self.last_synced_at_monotonic = 0.0
        self.current_trading_date = _today_vn()
        self.last_synced_at_vn: datetime | None = None

    def run_forever(self) -> None:
        acquire_worker_lock(self.owner_id)
        setting_services.save_t0_worker_status(
            {
                "ssiForeignPhase": "Starting",
                "lastError": None,
            }
        )
        try:
            while True:
                refresh_worker_lock(self.owner_id)
                self._tick()
                time.sleep(15)
        except Exception as ex:
            logger.exception("T0 foreign worker stopped with fatal error")
            setting_services.save_t0_worker_status(
                {
                    "ssiForeignPhase": "Failed",
                    "lastError": str(ex),
                }
            )
            raise
        finally:
            release_worker_lock(self.owner_id)
            setting_services.save_t0_worker_status(
                {
                    "ssiForeignPhase": "Stopped",
                }
            )

    def _tick(self) -> None:
        schedule = setting_services.get_t0_snapshot_schedule_config()
        enabled = bool(schedule.get("enabled", False))
        refresh_minutes = int(schedule.get("foreignRefreshMinutes") or 15)
        interval_seconds = max(60, refresh_minutes * 60)
        today = _today_vn()
        if today != self.current_trading_date:
            self.current_trading_date = today
            self.last_synced_at_monotonic = 0.0
            self.last_synced_at_vn = None
        purge_stale_foreign_states(today)

        if not enabled:
            setting_services.save_t0_worker_status(
                {
                    "ssiForeignPhase": "Disabled",
                    "foreignRefreshMinutes": refresh_minutes,
                    "foreignStartTime": schedule.get("foreignStartTime") or "09:15",
                    "foreignEndTime": schedule.get("foreignEndTime") or "15:00",
                    "nextForeignSyncAt": None,
                }
            )
            return

        start_time = str(schedule.get("foreignStartTime") or "09:15")
        end_time = str(schedule.get("foreignEndTime") or "15:00")
        now_vn = _now_vn()
        start_dt, end_dt = _window_bounds(now_vn, start_time, end_time)
        next_sync_at = _compute_next_sync_at(now_vn, start_time, end_time, refresh_minutes, self.last_synced_at_vn)

        if now_vn < start_dt or now_vn > end_dt:
            phase = f"Cho cua so {start_time} - {end_time}"
            setting_services.save_t0_worker_status(
                {
                    "ssiForeignPhase": phase,
                    "foreignRefreshMinutes": refresh_minutes,
                    "foreignStartTime": start_time,
                    "foreignEndTime": end_time,
                    "nextForeignSyncAt": next_sync_at.isoformat(),
                }
            )
            return

        now_monotonic = time.monotonic()
        if self.last_synced_at_monotonic and (now_monotonic - self.last_synced_at_monotonic) < interval_seconds:
            setting_services.save_t0_worker_status(
                {
                    "foreignRefreshMinutes": refresh_minutes,
                    "foreignStartTime": start_time,
                    "foreignEndTime": end_time,
                    "nextForeignSyncAt": next_sync_at.isoformat(),
                }
            )
            return

        setting_services.save_t0_worker_status(
            {
                "ssiForeignPhase": "Dang dong bo foreign T0 tu SSI board",
                "foreignRefreshMinutes": refresh_minutes,
                "foreignStartTime": start_time,
                "foreignEndTime": end_time,
                "nextForeignSyncAt": next_sync_at.isoformat(),
            }
        )
        payloads = fetch_foreign_board_snapshots()
        filtered_payloads = {ticker: payload for ticker, payload in payloads.items() if len((ticker or "").strip()) == 3}
        result = replace_foreign_state_rows(filtered_payloads, today)
        self.last_synced_at_monotonic = now_monotonic
        self.last_synced_at_vn = _now_vn()
        next_sync_at = _compute_next_sync_at(self.last_synced_at_vn, start_time, end_time, refresh_minutes, self.last_synced_at_vn)
        setting_services.save_t0_worker_status(
            {
                "ssiForeignPhase": f"SSI board da dong bo {result['count']} ma",
                "lastForeignSyncAt": result["fetchedAt"],
                "foreignRefreshMinutes": refresh_minutes,
                "foreignStartTime": start_time,
                "foreignEndTime": end_time,
                "nextForeignSyncAt": next_sync_at.isoformat(),
            }
        )
