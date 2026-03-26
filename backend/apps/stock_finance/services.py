"""Port of StockFinanceChartService (Vietstock sync)."""

from __future__ import annotations

import json
import random
import threading
import time
from datetime import datetime
from typing import Any

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.stocks import stock_queries
from apps.stocks.models import StockSymbol
from apps.stock_finance.assessment_service import upsert_generated_assessment
from apps.stocks.stock_symbol_service import get_history_sync_status
from apps.stock_finance.models import (
    StockFinanceChartAssessment,
    StockFinanceChartSnapshot,
    StockFinanceChartSyncJob,
    StockFinanceChartSyncJobItem,
)
from apps.stock_finance.vietstock_parser import extract_verification_token
from common.exceptions import BadRequestError, NotFoundError

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
)
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


def _invalidate_progress_cache() -> None:
    global _progress_cache
    with _progress_cache_lock:
        _progress_cache = None


def get_sync_status_dict() -> dict:
    ensure_recovery_checked()
    job = (
        StockFinanceChartSyncJob.objects.filter(status=STATUS_RUNNING).order_by("-updated_at").first()
        or StockFinanceChartSyncJob.objects.filter(status=STATUS_PENDING).order_by("-updated_at").first()
        or StockFinanceChartSyncJob.objects.filter(status=STATUS_INTERRUPTED).order_by("-updated_at").first()
        or StockFinanceChartSyncJob.objects.order_by("-updated_at").first()
    )
    bs = _cfg("APP_STOCK_FINANCE_CHART_BATCH_SIZE", 60)
    progress = _current_sync_progress()
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
        }
    return _job_to_status(job, progress)


def _current_sync_progress() -> dict[str, int]:
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


def _job_to_status(job: StockFinanceChartSyncJob, progress: dict[str, int] | None = None) -> dict:
    progress = progress or _current_sync_progress()
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
    }


def list_ticker_page(page: int, size: int, ticker: str | None) -> dict:
    ensure_recovery_checked()
    if page < 0:
        raise BadRequestError("Page must be >= 0")
    if size <= 0 or size > 200:
        raise BadRequestError("Size must be between 1 and 200")
    all_rows = stock_queries.search_ticker_summaries((ticker or "").strip().upper())
    total = len(all_rows)
    start = min(page * size, total)
    end = min(start + size, total)
    chunk = all_rows[start:end]
    items = []
    for row in chunk:
        rtypes = (row.get("report_types") or "").split(",") if row.get("report_types") else []
        rtypes = [x.strip() for x in rtypes if x.strip()]
        last = row.get("last_synced_at")
        items.append(
            {
                "stockSymbolId": row["stock_symbol_id"],
                "ticker": row["ticker"],
                "chartCount": int(row.get("chart_count") or 0),
                "reportTypes": rtypes,
                "lastSyncedAt": last.isoformat() if hasattr(last, "isoformat") and last else None,
            }
        )
    total_pages = (total + size - 1) // size if size else 0
    return {
        "items": items,
        "page": page,
        "size": size,
        "totalElements": total,
        "totalPages": total_pages,
    }


def get_by_ticker(ticker: str) -> dict:
    ensure_recovery_checked()
    if not (ticker or "").strip():
        raise BadRequestError("Ticker is required")
    t = ticker.strip().upper()
    snaps = (
        StockFinanceChartSnapshot.objects.filter(ticker__iexact=t)
        .select_related("stock_symbol")
        .order_by("report_type", "chart_menu_id")
    )
    if not snaps.exists():
        raise NotFoundError(f"No finance chart snapshots found for ticker {t}")
    first = snaps.first()
    assert first is not None
    sid = first.stock_symbol_id
    synced = max((s.updated_at for s in snaps if s.updated_at), default=None)
    assess = StockFinanceChartAssessment.objects.filter(ticker__iexact=t).first()
    overview = None
    if assess and (assess.overview_assessment or "").strip():
        overview = assess.overview_assessment.strip()
    if overview is None:
        for s in sorted(snaps, key=lambda x: x.updated_at or timezone.now(), reverse=True):
            if (s.company_assessment or "").strip():
                overview = s.company_assessment.strip()
                break
    items = []
    for s in snaps.order_by("report_type", "chart_menu_id"):
        items.append(_snapshot_item(s))
    return {
        "stockSymbolId": sid,
        "ticker": t,
        "snapshotCount": snaps.count(),
        "syncedAt": synced.isoformat() if synced else None,
        "overviewAssessment": overview,
        "items": items,
    }


def _snapshot_item(s: StockFinanceChartSnapshot) -> dict:
    return {
        "id": s.id,
        "stockSymbolId": s.stock_symbol_id,
        "ticker": s.ticker,
        "chartMenuId": s.chart_menu_id,
        "chartName": s.chart_name,
        "reportType": s.report_type,
        "reportPeriod": s.report_period,
        "companyAssessment": s.company_assessment,
        "processingStatus": s.processing_status,
        "dataJson": s.data_json,
        "createdAt": s.created_at.isoformat() if s.created_at else None,
        "updatedAt": s.updated_at.isoformat() if s.updated_at else None,
    }


def update_assessment(ticker: str, overview: str | None) -> dict:
    ensure_recovery_checked()
    if not (ticker or "").strip():
        raise BadRequestError("Ticker is required")
    t = ticker.strip().upper()
    sym = StockSymbol.objects.filter(ticker__iexact=t).first()
    if not sym:
        raise NotFoundError("Ticker not found")
    text = (overview or "").strip()
    now = timezone.now()
    if not text:
        StockFinanceChartAssessment.objects.filter(ticker__iexact=t).delete()
        return {
            "stockSymbolId": sym.id,
            "ticker": t,
            "overviewAssessment": None,
            "assessmentStatus": "EMPTY",
            "sourceSyncedAt": None,
            "updatedAt": now.isoformat(),
        }
    from django.db.models import Max

    latest_ts = StockFinanceChartSnapshot.objects.filter(ticker__iexact=t).aggregate(m=Max("updated_at"))["m"]
    obj, created = StockFinanceChartAssessment.objects.get_or_create(
        stock_symbol=sym,
        defaults={
            "ticker": t,
            "overview_assessment": text,
            "assessment_status": "READY",
            "source_synced_at": latest_ts,
            "created_at": now,
            "updated_at": now,
        },
    )
    if not created:
        obj.ticker = t
        obj.overview_assessment = text
        obj.assessment_status = "READY"
        obj.source_synced_at = latest_ts
        obj.updated_at = now
        obj.save()
    return {
        "stockSymbolId": sym.id,
        "ticker": t,
        "overviewAssessment": obj.overview_assessment,
        "assessmentStatus": obj.assessment_status,
        "sourceSyncedAt": obj.source_synced_at.isoformat() if obj.source_synced_at else None,
        "updatedAt": obj.updated_at.isoformat() if obj.updated_at else None,
    }


def _text(node: dict, field: str) -> str | None:
    v = node.get(field)
    if v is None:
        return None
    return str(v).strip() or None


def _long_val(node: dict, field: str) -> int:
    v = node.get(field)
    if v is None:
        raise BadRequestError(f"Missing field: {field}")
    return int(v)


def _nullable_int(node: dict, field: str) -> int | None:
    v = node.get(field)
    return None if v is None else int(v)


def _report_type(report_term_type_id: int | None) -> str:
    return "YEAR" if report_term_type_id == 1 else "QUARTER"


def _term_rank(term: str | None) -> int:
    if not term or not str(term).strip():
        return -999999
    term = str(term).strip()
    try:
        if term.startswith("Q"):
            parts = term.split("/")
            return int(parts[1]) * 10 + int(parts[0][1:])
        if term.startswith("N/"):
            return int(term[2:]) * 10 + 9
    except Exception:
        return -999999
    return -999999


def _latest_report_period(chart_details: list[dict]) -> str | None:
    best = None
    best_rank = -999999
    for node in chart_details:
        n = _text(node, "NormTerm")
        if not n:
            continue
        r = _term_rank(n)
        if r > best_rank:
            best_rank = r
            best = n
    return best


def _load_session(ticker: str) -> tuple[str, str]:
    page_url = f"https://finance.vietstock.vn/{ticker}/tai-chinh.htm?tab=CHART"
    r = requests.get(
        page_url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
        timeout=60,
    )
    r.raise_for_status()
    token = extract_verification_token(r.text, ticker)
    cookie_header = _cookie_header_from_response(r)
    return token, cookie_header


def _cookie_header_from_response(r: requests.Response) -> str:
    if not r.cookies:
        raise BadRequestError("Unable to establish Vietstock session")
    return "; ".join(f"{k}={v}" for k, v in r.cookies.items())


def _fetch_chart_payload(ticker: str, token: str, cookie_header: str) -> dict[str, Any]:
    body = "&".join(
        [
            "stockCode=" + requests.utils.quote(ticker, safe=""),
            "chartPageId=0",
            "__RequestVerificationToken=" + requests.utils.quote(token, safe=""),
            "isCatch=true",
            "languageId=1",
        ]
    )
    r = requests.post(
        "https://finance.vietstock.vn/FinanceChartPage/GetListChart_Page_Mapping_ByStockCode_Full",
        data=body,
        headers={
            "User-Agent": USER_AGENT,
            "Referer": f"https://finance.vietstock.vn/{ticker}/tai-chinh.htm?tab=CHART",
            "Origin": "https://finance.vietstock.vn",
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Accept": "*/*",
            "Cookie": cookie_header,
        },
        timeout=120,
    )
    r.raise_for_status()
    try:
        return r.json()
    except Exception:
        raise BadRequestError(f"Unable to parse Vietstock chart response for ticker {ticker}")


def _write_chart_json(chart_node: dict, chart_details: list[dict]) -> str:
    return json.dumps({"chart": chart_node, "details": chart_details})


def process_ticker(stock_symbol_id: int, ticker: str) -> None:
    t = ticker.strip().upper()
    token, cookies = _load_session(t)
    payload = _fetch_chart_payload(t, token, cookies)
    data = payload.get("data") or {}
    chart_nodes = data.get("InfoChart") or []
    detail_nodes = data.get("InfoChartDetail") or []
    if not isinstance(chart_nodes, list) or not isinstance(detail_nodes, list):
        raise BadRequestError(f"Vietstock chart payload is invalid for ticker {ticker}")

    chart_by_id: dict[int, dict] = {}
    for node in chart_nodes:
        chart_by_id[_long_val(node, "ChartMenuID")] = node

    detail_by_id: dict[int, list[dict]] = {}
    for node in detail_nodes:
        cid = _long_val(node, "ChartMenuID")
        detail_by_id.setdefault(cid, []).append(node)

    with transaction.atomic():
        sym = StockSymbol.objects.select_for_update().get(pk=stock_symbol_id)
        StockFinanceChartSnapshot.objects.filter(ticker__iexact=t).delete()
        snaps = []
        for chart_menu_id, chart_node in chart_by_id.items():
            details = detail_by_id.get(chart_menu_id, [])
            sn = StockFinanceChartSnapshot(
                stock_symbol=sym,
                ticker=t,
                chart_menu_id=chart_menu_id,
                chart_name=_text(chart_node, "NameChart") or "",
                report_type=_report_type(_nullable_int(chart_node, "ReportTermTypeID")),
                report_period=_latest_report_period(details),
                company_assessment=None,
                processing_status=SNAPSHOT_STATUS_RAW,
                data_json=_write_chart_json(chart_node, details),
                created_at=timezone.now(),
                updated_at=timezone.now(),
            )
            snaps.append(sn)
        StockFinanceChartSnapshot.objects.bulk_create(snaps)

    # Keep sync resilient: assessment generation should enrich data, not block snapshot persistence.
    try:
        upsert_generated_assessment(t)
    except Exception:
        pass


def _normalize_mode(mode: str | None) -> str:
    if not mode or not str(mode).strip():
        return MODE_SYNC_MISSING
    m = str(mode).strip().lower()
    if m in ("missing", "sync_missing", MODE_SYNC_MISSING.lower()):
        return MODE_SYNC_MISSING
    if m in ("reset", "reset_and_sync", MODE_RESET_AND_SYNC.lower()):
        return MODE_RESET_AND_SYNC
    raise BadRequestError("Unsupported sync mode")


def _next_batch_no() -> int:
    last = StockFinanceChartSyncJob.objects.order_by("-updated_at").first()
    return (last.batch_no + 1) if last else 1


def create_next_batch_job(mode: str) -> StockFinanceChartSyncJob:
    _invalidate_progress_cache()
    min_vol = _cfg("APP_STOCK_FINANCE_CHART_MIN_AVG_VOLUME_20", 100000)
    batch_size = _cfg("APP_STOCK_FINANCE_CHART_BATCH_SIZE", 60)
    eligible_raw = stock_queries.find_eligible_finance_chart_tickers(min_vol)
    eligible = list(eligible_raw)

    if mode == MODE_SYNC_MISSING:
        have = set(
            StockFinanceChartSnapshot.objects.values_list("ticker", flat=True).distinct()
        )
        have_u = {str(x).upper() for x in have}
        eligible = [e for e in eligible if str(e["ticker"]).upper() not in have_u]
    elif mode == MODE_RESET_AND_SYNC:
        StockFinanceChartSnapshot.objects.all().delete()
        StockFinanceChartAssessment.objects.all().delete()

    eff_bs = max(1, min(batch_size, len(eligible))) if eligible else 0
    now = timezone.now()
    job = StockFinanceChartSyncJob(
        mode=mode,
        status=STATUS_COMPLETED if not eligible else STATUS_PENDING,
        batch_no=_next_batch_no(),
        batch_size=eff_bs,
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

    syms = {s.id: s for s in StockSymbol.objects.filter(id__in=[e["stock_symbol_id"] for e in eligible])}
    items = []
    for e in eligible:
        sid = e["stock_symbol_id"]
        if sid not in syms:
            continue
        items.append(
            StockFinanceChartSyncJobItem(
                job=job,
                stock_symbol=syms[sid],
                ticker=str(e["ticker"]).upper(),
                status=STATUS_PENDING,
                attempt_count=0,
                created_at=now,
                updated_at=now,
            )
        )
    StockFinanceChartSyncJobItem.objects.bulk_create(items)
    return job


def _process_job(job_id: int) -> None:
    max_retries = max(1, _cfg("APP_STOCK_FINANCE_CHART_MAX_RETRIES", 2))
    max_consec = _cfg("APP_STOCK_FINANCE_CHART_MAX_CONSECUTIVE_FAILURES", 5)
    consec = 0
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
                    j = StockFinanceChartSyncJob.objects.select_for_update().get(pk=job_id)
                    j.status = STATUS_COMPLETED
                    j.finished_at = timezone.now()
                    j.save(update_fields=["status", "finished_at", "updated_at"])
                    return
                item.status = STATUS_RUNNING
                item.started_at = timezone.now()
                item.attempt_count += 1
                item.save(update_fields=["status", "started_at", "attempt_count", "updated_at"])
                item_id = item.id
                sym_id = item.stock_symbol_id
                tkr = item.ticker

            success = False
            last_err = None
            for attempt in range(1, max_retries + 1):
                try:
                    process_ticker(sym_id, tkr)
                    with transaction.atomic():
                        it = StockFinanceChartSyncJobItem.objects.get(pk=item_id)
                        it.status = STATUS_DONE
                        it.last_error = None
                        it.finished_at = timezone.now()
                        it.save(update_fields=["status", "last_error", "finished_at", "updated_at"])
                        j = StockFinanceChartSyncJob.objects.select_for_update().get(pk=job_id)
                        j.processed_count += 1
                        j.success_count += 1
                        j.save(update_fields=["processed_count", "success_count", "updated_at"])
                    _invalidate_progress_cache()
                    success = True
                    consec = 0
                    break
                except Exception as ex:
                    last_err = str(ex)
                    with transaction.atomic():
                        it = StockFinanceChartSyncJobItem.objects.get(pk=item_id)
                        it.last_error = last_err
                        it.status = STATUS_FAILED if attempt >= max_retries else STATUS_RUNNING
                        it.save(update_fields=["last_error", "status", "updated_at"])
                    if attempt < max_retries:
                        _sleep_s(_backoff_delay(attempt))
            if not success:
                with transaction.atomic():
                    j = StockFinanceChartSyncJob.objects.select_for_update().get(pk=job_id)
                    j.processed_count += 1
                    j.failed_count += 1
                    if last_err:
                        j.last_error = last_err
                    j.save(update_fields=["processed_count", "failed_count", "last_error", "updated_at"])
                consec += 1
                if consec >= max_consec:
                    with transaction.atomic():
                        j = StockFinanceChartSyncJob.objects.select_for_update().get(pk=job_id)
                        j.status = STATUS_INTERRUPTED
                        j.last_error = "Too many consecutive failures"
                        j.finished_at = timezone.now()
                        j.save(update_fields=["status", "last_error", "finished_at", "updated_at"])
                    _invalidate_progress_cache()
                    StockFinanceChartSyncJobItem.objects.filter(job_id=job_id, status=STATUS_RUNNING).update(
                        status=STATUS_PENDING, last_error="Reset after interrupt"
                    )
                    return
            _sleep_s(_random_delay())
    finally:
        with _worker_lock:
            global _worker_running
            _worker_running = False


def start_sync(requested_mode: str) -> dict:
    ensure_recovery_checked()
    _invalidate_progress_cache()
    hs = get_history_sync_status()
    if hs.get("running"):
        raise BadRequestError("Stock history sync is running. Please wait until it finishes.")
    mode = _normalize_mode(requested_mode)
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
        threading.Thread(target=_process_job, args=(job.id,), daemon=True).start()
        return {
            "jobId": job.id,
            "mode": job.mode,
            "status": job.status,
            "batchSize": job.batch_size,
            "eligibleCount": job.eligible_count,
        }
