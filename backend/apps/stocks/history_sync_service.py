from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum

from django.db.models import Max

from apps.stocks import money_flow_service as money_flow_services
from apps.stocks.models import StockHistory, StockSymbol
from apps.stocks.ssi_history_client import SsiHistoryClient
from apps.stocks.ssi_history_parser import parse_history_payload

HISTORY_BOOTSTRAP_SESSIONS = 200
HISTORY_BOOTSTRAP_CALENDAR_DAYS = 400
HISTORY_INCREMENTAL_OVERLAP_DAYS = 7
HISTORY_BOOTSTRAP_PAGE_SIZE = 260
HISTORY_MIN_HEALTHY_RECORDS = 20
HISTORY_TICKER_RESYNC_PAGE_SIZE = 40


class HistorySyncMode(str, Enum):
    RESET = "RESET"
    INCREMENTAL = "INCREMENTAL"


@dataclass
class HistoryFetchPlan:
    from_date: date
    page_size: int
    max_records: int | None
    delete_existing_window: bool


def resolve_history_plan(ticker: str, today: date, mode: HistorySyncMode) -> HistoryFetchPlan:
    if mode == HistorySyncMode.RESET:
        return HistoryFetchPlan(
            from_date=today - timedelta(days=HISTORY_BOOTSTRAP_CALENDAR_DAYS),
            page_size=HISTORY_BOOTSTRAP_PAGE_SIZE,
            max_records=HISTORY_BOOTSTRAP_SESSIONS,
            delete_existing_window=False,
        )

    history_count = StockHistory.objects.filter(ticker=ticker).count()
    if history_count < HISTORY_MIN_HEALTHY_RECORDS:
        return HistoryFetchPlan(
            from_date=today - timedelta(days=HISTORY_BOOTSTRAP_CALENDAR_DAYS),
            page_size=HISTORY_BOOTSTRAP_PAGE_SIZE,
            max_records=HISTORY_BOOTSTRAP_SESSIONS,
            delete_existing_window=False,
        )

    latest = StockHistory.objects.filter(ticker=ticker).aggregate(m=Max("trading_date"))["m"]
    if latest is None:
        return HistoryFetchPlan(
            from_date=today - timedelta(days=HISTORY_BOOTSTRAP_CALENDAR_DAYS),
            page_size=HISTORY_BOOTSTRAP_PAGE_SIZE,
            max_records=HISTORY_BOOTSTRAP_SESSIONS,
            delete_existing_window=False,
        )

    return HistoryFetchPlan(
        from_date=latest - timedelta(days=HISTORY_INCREMENTAL_OVERLAP_DAYS),
        page_size=max(HISTORY_INCREMENTAL_OVERLAP_DAYS + 10, 35),
        max_records=None,
        delete_existing_window=True,
    )


def run_history_sync(
    mode: HistorySyncMode,
    update_status: Callable[[bool, HistorySyncMode, int, int, int, int, int, str, str | None, str | None], None],
    client: SsiHistoryClient | None = None,
) -> None:
    http = client or SsiHistoryClient()
    today = date.today()
    tickers = [str(value).strip().upper() for value in StockSymbol.objects.order_by("ticker").values_list("ticker", flat=True) if value]
    total_symbols = len(tickers)
    processed_symbols = 0
    failed_symbols = 0
    records_updated = 0
    affected_dates: set[date] = set()
    days = HISTORY_BOOTSTRAP_SESSIONS if mode == HistorySyncMode.RESET else HISTORY_INCREMENTAL_OVERLAP_DAYS

    if mode == HistorySyncMode.RESET:
        update_status(True, mode, days, total_symbols, 0, 0, 0, "Deleting existing history", None, None)
        StockHistory.objects.all().delete()

    update_status(True, mode, days, total_symbols, 0, 0, 0, "Downloading + syncing", None, None)

    for ticker in tickers:
        try:
            plan = resolve_history_plan(ticker, today, mode)
            payload = http.fetch_histories(ticker, plan.from_date, plan.page_size)
            parsed = parse_history_payload(payload, ticker, plan.max_records)
            if plan.delete_existing_window:
                StockHistory.objects.filter(ticker=ticker, trading_date__gte=plan.from_date, trading_date__lte=today).delete()
            if parsed.histories:
                StockHistory.objects.bulk_create(parsed.histories, batch_size=500)
                affected_dates.update(item.trading_date for item in parsed.histories)
            records_updated += len(parsed.histories)
            processed_symbols += 1
            update_status(True, mode, days, total_symbols, processed_symbols, failed_symbols, records_updated, "Syncing", None, None)
        except Exception as exc:
            failed_symbols += 1
            update_status(True, mode, days, total_symbols, processed_symbols, failed_symbols, records_updated, "Syncing", str(exc), ticker)

    for affected_date in sorted(affected_dates):
        try:
            money_flow_services.rebuild_money_flow_eod_features(affected_date)
        except Exception:
            pass
    update_status(False, mode, days, total_symbols, processed_symbols, failed_symbols, records_updated, "Completed", None, None)


def resync_ticker_history(
    ticker: str,
    update_status: Callable[[bool, HistorySyncMode, int, int, int, int, int, str, str | None, str | None], None],
    client: SsiHistoryClient | None = None,
    target_sessions: int = HISTORY_BOOTSTRAP_SESSIONS,
) -> dict:
    normalized_ticker = (ticker or "").strip().upper()
    if not normalized_ticker:
        raise ValueError("Ticker is required")

    symbol_exists = StockSymbol.objects.filter(ticker__iexact=normalized_ticker).exists()
    if not symbol_exists:
        raise ValueError(f"Ticker not found: {normalized_ticker}")

    http = client or SsiHistoryClient()
    from_date = date.today() - timedelta(days=3650)
    by_date: dict[date, StockHistory] = {}
    page = 1

    update_status(True, HistorySyncMode.RESET, target_sessions, 1, 0, 0, 0, f"Resyncing {normalized_ticker}", None, None)

    while len(by_date) < target_sessions:
        payload = http.fetch_histories(normalized_ticker, from_date, HISTORY_TICKER_RESYNC_PAGE_SIZE, page=page)
        parsed = parse_history_payload(payload, normalized_ticker, None)
        histories = parsed.histories
        if not histories:
            break

        before_count = len(by_date)
        for history in histories:
            by_date[history.trading_date] = history

        if len(histories) < HISTORY_TICKER_RESYNC_PAGE_SIZE or len(by_date) == before_count:
            break
        page += 1

    histories_out = sorted(by_date.values(), key=lambda item: item.trading_date, reverse=True)[:target_sessions]
    histories_out = sorted(histories_out, key=lambda item: item.trading_date)

    if histories_out:
        min_date = histories_out[0].trading_date
        max_date = histories_out[-1].trading_date
        StockHistory.objects.filter(
            ticker=normalized_ticker,
            trading_date__gte=min_date,
            trading_date__lte=max_date,
        ).delete()
        StockHistory.objects.bulk_create(histories_out, batch_size=500)
        for affected_date in sorted({item.trading_date for item in histories_out}):
            try:
                money_flow_services.rebuild_money_flow_eod_features(affected_date)
            except Exception:
                pass

    update_status(
        False,
        HistorySyncMode.RESET,
        target_sessions,
        1,
        1,
        0,
        len(histories_out),
        "Completed",
        None,
        None,
    )
    return {
        "ticker": normalized_ticker,
        "recordsUpdated": len(histories_out),
        "pagesFetched": page,
        "targetSessions": target_sessions,
    }
