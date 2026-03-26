from __future__ import annotations

import logging
import random
import threading
import time

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.stocks import stock_queries
from apps.stocks.models import StockSymbol
from apps.stock_finance.assessment_service import upsert_generated_assessment
from apps.stock_finance.models import (
    StockFinanceChartAssessment,
    StockFinanceChartSnapshot,
    StockFinanceChartSyncJob,
    StockFinanceChartSyncJobItem,
)
from apps.stock_finance.vietstock_client import VietstockClient
from apps.stock_finance.vietstock_parser import (
    extract_verification_token,
    latest_report_period,
    nullable_int,
    parse_chart_payload,
    report_type,
    text,
    write_chart_json,
)
from common.exceptions import BadRequestError

logger = logging.getLogger(__name__)

MODE_ROLLING_BATCH = "ROLLING_BATCH"
MODE_SYNC_MISSING = "SYNC_MISSING"
MODE_RESET_AND_SYNC = "RESET_AND_SYNC"
STATUS_PENDING = "PENDING"
STATUS_RUNNING = "RUNNING"
STATUS_DONE = "DONE"
STATUS_FAILED = "FAILED"
STATUS_SKIPPED = "SKIPPED"
STATUS_COMPLETED = "COMPLETED"
STATUS_INTERRUPTED = "INTERRUPTED"
SNAPSHOT_STATUS_RAW = "RAW"

_worker_lock = threading.Lock()
_worker_running = False
_recovery_lock = threading.Lock()
_recovery_checked = False
_progress_cache_lock = threading.Lock()
_progress_cache: dict[str, int | float] | None = None
_progress_cache_ttl_s = 15


def _cfg(name: str, default: int) -> int:
    return int(getattr(settings, name, default))


def _random_delay() -> float:
    lo = _cfg("APP_STOCK_FINANCE_CHART_MIN_DELAY_MS", 2000) / 1000.0
    hi = _cfg("APP_STOCK_FINANCE_CHART_MAX_DELAY_MS", 6000) / 1000.0
    if hi <= lo:
        return lo
    return random.uniform(lo, hi)


def _backoff_delay(attempt: int) -> float:
    base = max(1000, _cfg("APP_STOCK_FINANCE_CHART_MIN_DELAY_MS", 2000))
    delay = base * (1 << max(0, attempt - 1))
    return min(delay, 15000) / 1000.0


def _sleep_s(sec: float) -> None:
    time.sleep(sec)


def invalidate_progress_cache() -> None:
    global _progress_cache
    with _progress_cache_lock:
        _progress_cache = None


def recover_interrupted_jobs() -> None:
    for job in StockFinanceChartSyncJob.objects.filter(status=STATUS_RUNNING):
        job.status = STATUS_INTERRUPTED
        job.last_error = "Recovered after application restart"
        job.save(update_fields=["status", "last_error", "updated_at"])
        for item in StockFinanceChartSyncJobItem.objects.filter(job_id=job.id, status=STATUS_RUNNING):
            item.status = STATUS_PENDING
            item.last_error = "Reset after application restart"
            item.finished_at = None
            item.save(update_fields=["status", "last_error", "finished_at", "updated_at"])


def ensure_recovery_checked() -> None:
    global _recovery_checked
    if _recovery_checked:
        return
    with _recovery_lock:
        if _recovery_checked:
            return
        recover_interrupted_jobs()
        _recovery_checked = True


def current_sync_progress() -> dict[str, int]:
    global _progress_cache
    now = time.time()
    with _progress_cache_lock:
        cached = _progress_cache
        if cached and (now - float(cached["computedAt"])) < _progress_cache_ttl_s:
            return {
                "totalEligibleCount": int(cached["totalEligibleCount"]),
                "existingCount": int(cached["existingCount"]),
            }

    min_vol = _cfg("APP_STOCK_FINANCE_CHART_MIN_AVG_VOLUME_20", 100000)
    progress = stock_queries.get_eligible_finance_chart_progress(min_vol)
    with _progress_cache_lock:
        _progress_cache = {
            "computedAt": now,
            "totalEligibleCount": progress["totalEligibleCount"],
            "existingCount": progress["existingCount"],
        }
    return progress


def current_running_ticker(job_id: int | None) -> str | None:
    if not job_id:
        return None
    item = (
        StockFinanceChartSyncJobItem.objects.filter(job_id=job_id, status=STATUS_RUNNING)
        .order_by("-updated_at")
        .first()
    )
    return item.ticker if item else None


def job_to_status(job: StockFinanceChartSyncJob, progress: dict[str, int] | None = None) -> dict:
    progress = progress or current_sync_progress()
    return {
        "jobId": job.id,
        "mode": job.mode,
        "status": job.status,
        "batchNo": job.batch_no,
        "batchSize": job.batch_size,
        "eligibleCount": job.eligible_count,
        "processedCount": job.processed_count,
        "successCount": job.success_count,
        "failedCount": job.failed_count,
        "skippedCount": job.skipped_count,
        "totalEligibleCount": progress["totalEligibleCount"],
        "existingCount": progress["existingCount"],
        "startedAt": job.started_at.isoformat() if job.started_at else None,
        "finishedAt": job.finished_at.isoformat() if job.finished_at else None,
        "lastError": job.last_error,
        "currentTicker": current_running_ticker(job.id),
    }


def get_sync_status_dict() -> dict:
    ensure_recovery_checked()
    job = (
        StockFinanceChartSyncJob.objects.filter(status=STATUS_RUNNING).order_by("-updated_at").first()
        or StockFinanceChartSyncJob.objects.filter(status=STATUS_PENDING).order_by("-updated_at").first()
        or StockFinanceChartSyncJob.objects.filter(status=STATUS_INTERRUPTED).order_by("-updated_at").first()
        or StockFinanceChartSyncJob.objects.order_by("-updated_at").first()
    )
    bs = _cfg("APP_STOCK_FINANCE_CHART_BATCH_SIZE", 60)
    progress = current_sync_progress()
    if job is None:
        return {
            "jobId": None,
            "mode": MODE_SYNC_MISSING,
            "status": "IDLE",
            "batchNo": 0,
            "batchSize": bs,
            "eligibleCount": 0,
            "processedCount": 0,
            "successCount": 0,
            "failedCount": 0,
            "skippedCount": 0,
            "totalEligibleCount": progress["totalEligibleCount"],
            "existingCount": progress["existingCount"],
            "startedAt": None,
            "finishedAt": None,
            "lastError": None,
            "currentTicker": None,
        }
    return job_to_status(job, progress)


def load_vietstock_session(ticker: str, client: VietstockClient | None = None) -> tuple[str, str]:
    http = client or VietstockClient()
    response = http.load_session_page(ticker)
    token = extract_verification_token(response.text, ticker)
    cookie_header = http.build_cookie_header(response)
    return token, cookie_header


def process_ticker(stock_symbol_id: int, ticker: str, client: VietstockClient | None = None) -> None:
    normalized = ticker.strip().upper()
    http = client or VietstockClient()
    token, cookies = load_vietstock_session(normalized, http)
    payload = http.fetch_chart_payload(normalized, token, cookies)
    chart_by_id, detail_by_id = parse_chart_payload(payload, normalized)

    with transaction.atomic():
        symbol = StockSymbol.objects.select_for_update().get(pk=stock_symbol_id)
        StockFinanceChartSnapshot.objects.filter(ticker__iexact=normalized).delete()
        snapshots = []
        now = timezone.now()
        for chart_menu_id, chart_node in chart_by_id.items():
            details = detail_by_id.get(chart_menu_id, [])
            snapshots.append(
                StockFinanceChartSnapshot(
                    stock_symbol=symbol,
                    ticker=normalized,
                    chart_menu_id=chart_menu_id,
                    chart_name=text(chart_node, "NameChart") or "",
                    report_type=report_type(nullable_int(chart_node, "ReportTermTypeID")),
                    report_period=latest_report_period(details),
                    company_assessment=None,
                    processing_status=SNAPSHOT_STATUS_RAW,
                    data_json=write_chart_json(chart_node, details),
                    created_at=now,
                    updated_at=now,
                )
            )
        StockFinanceChartSnapshot.objects.bulk_create(snapshots)

    try:
        upsert_generated_assessment(normalized)
    except Exception as exc:
        logger.warning("Finance chart assessment generation failed for %s: %s", normalized, exc)


def normalize_mode(mode: str | None) -> str:
    if not mode or not str(mode).strip():
        return MODE_SYNC_MISSING
    value = str(mode).strip().lower()
    if value in ("missing", "sync_missing", MODE_SYNC_MISSING.lower()):
        return MODE_SYNC_MISSING
    if value in ("reset", "reset_and_sync", MODE_RESET_AND_SYNC.lower()):
        return MODE_RESET_AND_SYNC
    raise BadRequestError("Unsupported sync mode")


def next_batch_no() -> int:
    last = StockFinanceChartSyncJob.objects.order_by("-updated_at").first()
    return (last.batch_no + 1) if last else 1


def create_next_batch_job(mode: str) -> StockFinanceChartSyncJob:
    invalidate_progress_cache()
    min_vol = _cfg("APP_STOCK_FINANCE_CHART_MIN_AVG_VOLUME_20", 100000)
    batch_size = _cfg("APP_STOCK_FINANCE_CHART_BATCH_SIZE", 60)
    eligible_raw = stock_queries.find_eligible_finance_chart_tickers(min_vol)
    eligible = list(eligible_raw)

    if mode == MODE_SYNC_MISSING:
        have = set(StockFinanceChartSnapshot.objects.values_list("ticker", flat=True).distinct())
        have_u = {str(value).upper() for value in have}
        eligible = [row for row in eligible if str(row["ticker"]).upper() not in have_u]
    elif mode == MODE_RESET_AND_SYNC:
        StockFinanceChartSnapshot.objects.all().delete()
        StockFinanceChartAssessment.objects.all().delete()

    effective_batch_size = max(1, min(batch_size, len(eligible))) if eligible else 0
    now = timezone.now()
    job = StockFinanceChartSyncJob(
        mode=mode,
        status=STATUS_COMPLETED if not eligible else STATUS_PENDING,
        batch_no=next_batch_no(),
        batch_size=effective_batch_size,
        eligible_count=len(eligible),
        processed_count=0,
        success_count=0,
        failed_count=0,
        skipped_count=0,
        started_at=now if not eligible else None,
        finished_at=now if not eligible else None,
        last_error=None,
        created_at=now,
        updated_at=now,
    )
    job.save()
    if not eligible:
        return job

    symbols = {item.id: item for item in StockSymbol.objects.filter(id__in=[row["stock_symbol_id"] for row in eligible])}
    items = []
    for row in eligible:
        sid = row["stock_symbol_id"]
        if sid not in symbols:
            continue
        items.append(
            StockFinanceChartSyncJobItem(
                job=job,
                stock_symbol=symbols[sid],
                ticker=str(row["ticker"]).upper(),
                status=STATUS_PENDING,
                attempt_count=0,
                created_at=now,
                updated_at=now,
            )
        )
    StockFinanceChartSyncJobItem.objects.bulk_create(items)
    return job


def process_job(job_id: int) -> None:
    max_retries = max(1, _cfg("APP_STOCK_FINANCE_CHART_MAX_RETRIES", 2))
    max_consecutive_failures = _cfg("APP_STOCK_FINANCE_CHART_MAX_CONSECUTIVE_FAILURES", 5)
    consecutive_failures = 0
    client = VietstockClient()
    try:
        with transaction.atomic():
            job = StockFinanceChartSyncJob.objects.select_for_update().get(pk=job_id)
            job.status = STATUS_RUNNING
            if job.started_at is None:
                job.started_at = timezone.now()
            job.save(update_fields=["status", "started_at", "updated_at"])
        while True:
            with transaction.atomic():
                item = (
                    StockFinanceChartSyncJobItem.objects.select_for_update()
                    .filter(job_id=job_id, status=STATUS_PENDING)
                    .order_by("ticker")
                    .first()
                )
                if item is None:
                    job = StockFinanceChartSyncJob.objects.select_for_update().get(pk=job_id)
                    job.status = STATUS_COMPLETED
                    job.finished_at = timezone.now()
                    job.save(update_fields=["status", "finished_at", "updated_at"])
                    return
                item.status = STATUS_RUNNING
                item.started_at = timezone.now()
                item.attempt_count += 1
                item.save(update_fields=["status", "started_at", "attempt_count", "updated_at"])
                item_id = item.id
                symbol_id = item.stock_symbol_id
                ticker = item.ticker

            success = False
            last_error = None
            for attempt in range(1, max_retries + 1):
                try:
                    process_ticker(symbol_id, ticker, client)
                    with transaction.atomic():
                        item = StockFinanceChartSyncJobItem.objects.get(pk=item_id)
                        item.status = STATUS_DONE
                        item.last_error = None
                        item.finished_at = timezone.now()
                        item.save(update_fields=["status", "last_error", "finished_at", "updated_at"])
                        job = StockFinanceChartSyncJob.objects.select_for_update().get(pk=job_id)
                        job.processed_count += 1
                        job.success_count += 1
                        job.last_error = None
                        job.save(update_fields=["processed_count", "success_count", "last_error", "updated_at"])
                    invalidate_progress_cache()
                    success = True
                    consecutive_failures = 0
                    break
                except Exception as exc:
                    last_error = f"{ticker}: {exc}"
                    logger.warning("Vietstock sync failed for %s on attempt %s: %s", ticker, attempt, exc)
                    with transaction.atomic():
                        item = StockFinanceChartSyncJobItem.objects.get(pk=item_id)
                        item.last_error = str(exc)
                        item.status = STATUS_FAILED if attempt >= max_retries else STATUS_RUNNING
                        item.save(update_fields=["last_error", "status", "updated_at"])
                    if attempt < max_retries:
                        _sleep_s(_backoff_delay(attempt))
            if not success:
                with transaction.atomic():
                    job = StockFinanceChartSyncJob.objects.select_for_update().get(pk=job_id)
                    job.processed_count += 1
                    job.failed_count += 1
                    if last_error:
                        job.last_error = last_error
                    job.save(update_fields=["processed_count", "failed_count", "last_error", "updated_at"])
                consecutive_failures += 1
                if consecutive_failures >= max_consecutive_failures:
                    with transaction.atomic():
                        job = StockFinanceChartSyncJob.objects.select_for_update().get(pk=job_id)
                        job.status = STATUS_INTERRUPTED
                        job.last_error = "Too many consecutive failures"
                        job.finished_at = timezone.now()
                        job.save(update_fields=["status", "last_error", "finished_at", "updated_at"])
                    invalidate_progress_cache()
                    StockFinanceChartSyncJobItem.objects.filter(job_id=job_id, status=STATUS_RUNNING).update(
                        status=STATUS_PENDING,
                        last_error="Reset after interrupt",
                    )
                    return
            _sleep_s(_random_delay())
    finally:
        with _worker_lock:
            global _worker_running
            _worker_running = False


def start_sync(requested_mode: str, history_status_getter) -> dict:
    ensure_recovery_checked()
    invalidate_progress_cache()
    history_status = history_status_getter()
    if history_status.get("running"):
        raise BadRequestError("Stock history sync is running. Please wait until it finishes.")
    mode = normalize_mode(requested_mode)
    with _worker_lock:
        global _worker_running
        if StockFinanceChartSyncJob.objects.filter(status=STATUS_RUNNING).exists() or _worker_running:
            job = StockFinanceChartSyncJob.objects.order_by("-updated_at").first()
            if job:
                return {
                    "jobId": job.id,
                    "mode": job.mode,
                    "status": job.status,
                    "batchSize": job.batch_size,
                    "eligibleCount": job.eligible_count,
                }
            raise BadRequestError("Sync is already running")
        job = create_next_batch_job(mode)
        if job.eligible_count == 0:
            return {
                "jobId": job.id,
                "mode": job.mode,
                "status": job.status,
                "batchSize": job.batch_size,
                "eligibleCount": 0,
            }
        _worker_running = True
        threading.Thread(target=process_job, args=(job.id,), daemon=True).start()
        return {
            "jobId": job.id,
            "mode": job.mode,
            "status": job.status,
            "batchSize": job.batch_size,
            "eligibleCount": job.eligible_count,
        }
