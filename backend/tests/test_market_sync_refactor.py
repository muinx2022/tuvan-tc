from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from apps.stocks.history_sync_service import HistoryFetchPlan, HistorySyncMode, resync_ticker_history, run_history_sync
from apps.stocks.ssi_history_parser import ParsedHistoryBatch, parse_trading_date
from apps.stocks.vps_parser import parse_company_basic_payload


class VpsParserTests(SimpleTestCase):
    def test_parse_company_basic_payload_dedupes_by_ticker(self):
        rows, received = parse_company_basic_payload(
            {
                "data": [
                    {"Ticker": "aaa", "OrganName": "Old", "IcbName2": "Bank"},
                    {"Ticker": "AAA", "OrganName": "New", "IcbName2": "Bank"},
                    {"Ticker": "BBB", "OrganName": "B Corp", "IcbName2": "Retail"},
                ]
            }
        )

        self.assertEqual(received, 3)
        self.assertEqual([row.ticker for row in rows], ["AAA", "BBB"])
        self.assertEqual(rows[0].organ_name, "New")


class SsiHistoryParserTests(SimpleTestCase):
    def test_parse_trading_date_supports_iso_and_vn_format(self):
        self.assertEqual(str(parse_trading_date("2026-03-21T00:00:00")), "2026-03-21")
        self.assertEqual(str(parse_trading_date("21/03/2026")), "2026-03-21")


class HistorySyncServiceTests(SimpleTestCase):
    def test_incremental_sync_fetches_before_deleting_existing_window(self):
        events: list[str] = []
        status_updates: list[tuple] = []

        class _Client:
            def fetch_histories(self, ticker, from_date, page_size):
                events.append(f"fetch:{ticker}")
                return {"data": []}

        filter_result = Mock()
        filter_result.delete.side_effect = lambda: events.append("delete:AAA")

        with patch("apps.stocks.history_sync_service.StockSymbol.objects.order_by") as order_by_mock, \
            patch("apps.stocks.history_sync_service.resolve_history_plan") as resolve_plan_mock, \
            patch("apps.stocks.history_sync_service.parse_history_payload") as parse_payload_mock, \
            patch("apps.stocks.history_sync_service.StockHistory.objects.filter", return_value=filter_result), \
            patch("apps.stocks.history_sync_service.StockHistory.objects.bulk_create") as bulk_create_mock:
            order_by_mock.return_value.values_list.return_value = ["AAA"]
            resolve_plan_mock.return_value = HistoryFetchPlan(
                from_date=parse_trading_date("2026-03-01"),
                page_size=35,
                max_records=None,
                delete_existing_window=True,
            )
            parse_payload_mock.side_effect = lambda payload, ticker, max_records: (
                events.append(f"parse:{ticker}") or ParsedHistoryBatch(histories=[])
            )

            run_history_sync(
                HistorySyncMode.INCREMENTAL,
                lambda *args: status_updates.append(args),
                client=_Client(),
            )

        self.assertEqual(events, ["fetch:AAA", "parse:AAA", "delete:AAA"])
        bulk_create_mock.assert_not_called()
        self.assertEqual(status_updates[-1][0], False)
        self.assertEqual(status_updates[-1][7], "Completed")

    def test_incremental_sync_reports_failed_ticker(self):
        status_updates: list[tuple] = []

        class _Client:
            def fetch_histories(self, ticker, from_date, page_size):
                raise RuntimeError("SSI unavailable")

        with patch("apps.stocks.history_sync_service.StockSymbol.objects.order_by") as order_by_mock, \
            patch("apps.stocks.history_sync_service.resolve_history_plan") as resolve_plan_mock:
            order_by_mock.return_value.values_list.return_value = ["AAA"]
            resolve_plan_mock.return_value = HistoryFetchPlan(
                from_date=parse_trading_date("2026-03-01"),
                page_size=35,
                max_records=None,
                delete_existing_window=True,
            )

            run_history_sync(
                HistorySyncMode.INCREMENTAL,
                lambda *args: status_updates.append(args),
                client=_Client(),
            )

        self.assertEqual(status_updates[-2][5], 1)
        self.assertEqual(status_updates[-2][8], "SSI unavailable")
        self.assertEqual(status_updates[-2][9], "AAA")

    def test_resync_ticker_history_fetches_multiple_pages(self):
        status_updates: list[tuple] = []
        filter_result = Mock()
        filter_result.delete = Mock()

        class _Client:
            def __init__(self):
                self.pages: list[int] = []

            def fetch_histories(self, ticker, from_date, page_size, page=1):
                self.pages.append(page)
                if page <= 5:
                    base_date = date(2026, 3, 21) - timedelta(days=(page - 1) * 40)
                    return {
                        "data": [
                            {
                                "tradingDate": (base_date - timedelta(days=index)).strftime("%d/%m/%Y"),
                                "close": str(index + (page - 1) * 40),
                            }
                            for index in range(40)
                        ]
                    }
                return {"data": []}

        client = _Client()

        with patch("apps.stocks.history_sync_service.StockSymbol.objects.filter") as symbol_filter_mock, \
            patch("apps.stocks.history_sync_service.StockHistory.objects.filter", return_value=filter_result), \
            patch("apps.stocks.history_sync_service.StockHistory.objects.bulk_create") as bulk_create_mock:
            symbol_filter_mock.return_value.exists.return_value = True

            result = resync_ticker_history(
                "AAA",
                lambda *args: status_updates.append(args),
                client=client,
            )

        self.assertEqual(client.pages, [1, 2, 3, 4, 5])
        self.assertEqual(result["ticker"], "AAA")
        self.assertEqual(result["targetSessions"], 200)
        self.assertEqual(status_updates[-1][7], "Completed")
        bulk_create_mock.assert_called_once()
        filter_result.delete.assert_called_once()
