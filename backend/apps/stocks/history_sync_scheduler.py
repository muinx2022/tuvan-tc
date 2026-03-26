from __future__ import annotations

import logging
import threading
import time
from datetime import datetime

from common.exceptions import BadRequestError

logger = logging.getLogger(__name__)

_scheduler_lock = threading.Lock()
_scheduler_started = False


def _should_run(now: datetime, config: dict, runtime: dict) -> bool:
    if not config.get("enabled"):
        return False
    scheduled_at = now.replace(
        hour=int(config.get("hour", 0)),
        minute=int(config.get("minute", 0)),
        second=0,
        microsecond=0,
    )
    if now < scheduled_at:
        return False
    return runtime.get("lastAttemptedDate") != now.date().isoformat()


def _scheduler_loop() -> None:
    while True:
        try:
            from apps.settings_app.services import (
                get_history_sync_runtime,
                get_history_sync_schedule_config,
                save_history_sync_runtime,
            )
            from apps.stocks import stock_symbol_service as stock_service

            now = datetime.now()
            config = get_history_sync_schedule_config()
            runtime = get_history_sync_runtime()
            if _should_run(now, config, runtime):
                current_date = now.date().isoformat()
                try:
                    stock_service.start_history_sync()
                    save_history_sync_runtime(
                        {
                            "lastAttemptedDate": current_date,
                            "lastStartedAt": now.isoformat(),
                            "lastError": None,
                        }
                    )
                    logger.info(
                        "Started scheduled stock history sync at %s for %02d:%02d",
                        now.isoformat(),
                        config.get("hour", 0),
                        config.get("minute", 0),
                    )
                except BadRequestError as exc:
                    save_history_sync_runtime(
                        {
                            "lastAttemptedDate": current_date,
                            "lastError": str(exc),
                        }
                    )
                    logger.warning("Skipped scheduled stock history sync: %s", exc)
                except Exception as exc:
                    save_history_sync_runtime(
                        {
                            "lastAttemptedDate": current_date,
                            "lastError": str(exc),
                        }
                    )
                    logger.exception("Scheduled stock history sync failed to start")
        except Exception:
            logger.exception("History sync scheduler loop failed")
        time.sleep(30)


def start_scheduler() -> None:
    global _scheduler_started
    with _scheduler_lock:
        if _scheduler_started:
            return
        threading.Thread(target=_scheduler_loop, name="stock-history-sync-scheduler", daemon=True).start()
        _scheduler_started = True
