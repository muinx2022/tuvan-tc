from __future__ import annotations

from rest_framework.response import Response

from apps.stocks import serializers as stock_serializers
from apps.stocks import stock_symbol_service as ss
from apps.stocks import t0_snapshot_service as t0s
from common.admin_api import AdminOnlyAPIView
from common.response import api_ok


class StockSyncView(AdminOnlyAPIView):
    def post(self, request):
        return Response(api_ok("Stock symbols synced successfully", ss.sync_from_vps()))


class StockSyncStatusView(AdminOnlyAPIView):
    def get(self, request):
        return Response(api_ok("Fetched stock sync status", ss.get_sync_status()))


class StockHistorySyncView(AdminOnlyAPIView):
    def post(self, request):
        return Response(api_ok("Stock history sync started", ss.start_history_sync()))


class StockHistorySyncResetView(AdminOnlyAPIView):
    def post(self, request):
        return Response(api_ok("Stock history reset sync started", ss.start_history_reset_sync()))


class StockHistorySyncStatusView(AdminOnlyAPIView):
    def get(self, request):
        return Response(api_ok("Fetched stock history sync status", ss.get_history_sync_status()))


class StockHistoryTickerResyncView(AdminOnlyAPIView):
    def post(self, request, ticker: str):
        return Response(api_ok("Stock history resynced successfully", ss.resync_history_for_ticker(ticker)))


class StockSymbolListView(AdminOnlyAPIView):
    def get(self, request):
        query = self.validate_query(stock_serializers.StockListQuerySerializer, partial=True)
        return Response(
            api_ok(
                "Fetched stock symbols successfully",
                ss.list_symbols(
                    query.get("page", 0),
                    query.get("size", 20),
                    query.get("ticker"),
                    query.get("industryGroupId"),
                ),
            )
        )


class StockIndustryGroupsView(AdminOnlyAPIView):
    def get(self, request):
        return Response(api_ok("Fetched stock industry groups successfully", ss.list_industry_groups()))


class StockTickersView(AdminOnlyAPIView):
    def get(self, request):
        return Response(api_ok("Fetched stock tickers successfully", ss.list_tickers()))


class StockHistoryByTickerView(AdminOnlyAPIView):
    def get(self, request, ticker: str):
        query = self.validate_query(stock_serializers.StockHistoryQuerySerializer, partial=True)
        return Response(api_ok("Fetched stock history successfully", ss.list_history(ticker, query.get("page", 0), query.get("size", 20))))


class StockAnalyticsIndustryView(AdminOnlyAPIView):
    def get(self, request):
        query = self.validate_query(stock_serializers.IndustryAnalyticsQuerySerializer, partial=True)
        return Response(api_ok("Fetched industry analytics successfully", ss.analytics_by_industry(query.get("industryGroupId"))))


class StockAnalyticsTickerView(AdminOnlyAPIView):
    def get(self, request):
        query = self.validate_query(stock_serializers.TickerAnalyticsQuerySerializer)
        return Response(api_ok("Fetched ticker analytics successfully", ss.analytics_by_ticker(query["ticker"])))


class StockIndustryAllocationView(AdminOnlyAPIView):
    def get(self, request):
        query = self.validate_query(stock_serializers.AllocationQuerySerializer, partial=True)
        return Response(api_ok("Fetched industry allocation analytics successfully", ss.analytics_industry_allocation(query.get("topN", 8))))


class StockTickerAllocationView(AdminOnlyAPIView):
    def get(self, request):
        query = self.validate_query(stock_serializers.TickerAllocationQuerySerializer, partial=True)
        return Response(
            api_ok(
                "Fetched ticker allocation analytics successfully",
                ss.analytics_ticker_allocation(query.get("ticker") or "", query.get("topN", 8)),
            )
        )


class StockT0StatusView(AdminOnlyAPIView):
    def get(self, request):
        return Response(api_ok("Fetched T0 worker status successfully", t0s.get_t0_status()))


class StockT0SnapshotListView(AdminOnlyAPIView):
    def get(self, request):
        query = self.validate_query(stock_serializers.T0SnapshotListQuerySerializer, partial=True)
        return Response(
            api_ok(
                "Fetched T0 snapshot groups successfully",
                t0s.list_t0_snapshot_groups(
                    query.get("page", 0),
                    query.get("size", 20),
                    query.get("ticker"),
                    query.get("tradingDate"),
                ),
            )
        )


class StockT0RealtimeListView(AdminOnlyAPIView):
    def get(self, request):
        query = self.validate_query(stock_serializers.T0SnapshotListQuerySerializer, partial=True)
        return Response(
            api_ok(
                "Fetched T0 realtime groups successfully",
                t0s.list_t0_realtime_groups(
                    query.get("page", 0),
                    query.get("size", 20),
                    query.get("ticker"),
                    query.get("tradingDate"),
                ),
            )
        )


class StockT0TickerTimelineView(AdminOnlyAPIView):
    def get(self, request, ticker: str):
        query = self.validate_query(stock_serializers.T0SnapshotTimelineQuerySerializer, partial=True)
        return Response(
            api_ok(
                "Fetched T0 ticker timeline successfully",
                t0s.get_t0_ticker_timeline(ticker, query.get("tradingDate")),
            )
        )


class StockForeignTradingListView(AdminOnlyAPIView):
    def get(self, request):
        query = self.validate_query(stock_serializers.ForeignTradingListQuerySerializer, partial=True)
        return Response(
            api_ok(
                "Fetched foreign trading successfully",
                ss.list_foreign_trading(
                    query.get("page", 0),
                    query.get("size", 20),
                    query.get("ticker"),
                    query.get("industryGroupId"),
                    query.get("tradingDate"),
                ),
            )
        )


class StockForeignTradingTickerTimelineView(AdminOnlyAPIView):
    def get(self, request, ticker: str):
        query = self.validate_query(stock_serializers.ForeignTradingTimelineQuerySerializer, partial=True)
        return Response(
            api_ok(
                "Fetched foreign trading ticker timeline successfully",
                ss.get_foreign_trading_ticker_timeline(
                    ticker,
                    query.get("page", 0),
                    query.get("size", 60),
                    query.get("tradingDateFrom"),
                    query.get("tradingDateTo"),
                ),
            )
        )
