from __future__ import annotations

from rest_framework.response import Response

from apps.stock_finance import services as sf
from apps.stock_finance.serializers import (
    FinanceChartAssessmentWriteSerializer,
    FinanceChartSyncStartQuerySerializer,
    FinanceChartTickerListQuerySerializer,
)
from common.admin_api import AdminOnlyAPIView
from common.response import api_ok


class FinanceChartSyncStartView(AdminOnlyAPIView):
    def post(self, request):
        query = self.validate_query(FinanceChartSyncStartQuerySerializer, partial=True)
        return Response(api_ok("Started Vietstock finance chart sync successfully", sf.start_sync(query.get("mode", "missing"))))


class FinanceChartSyncStatusView(AdminOnlyAPIView):
    def get(self, request):
        return Response(api_ok("Fetched Vietstock finance chart sync status successfully", sf.get_sync_status_dict()))


class FinanceChartTickerListView(AdminOnlyAPIView):
    def get(self, request):
        query = self.validate_query(FinanceChartTickerListQuerySerializer, partial=True)
        return Response(
            api_ok(
                "Fetched Vietstock finance chart tickers successfully",
                sf.list_ticker_page(query.get("page", 0), query.get("size", 20), query.get("ticker")),
            )
        )


class FinanceChartByTickerView(AdminOnlyAPIView):
    def get(self, request, ticker: str):
        return Response(api_ok("Fetched Vietstock finance charts successfully", sf.get_by_ticker(ticker)))


class FinanceChartAssessmentView(AdminOnlyAPIView):
    def put(self, request, ticker: str):
        d = self.validate_body(FinanceChartAssessmentWriteSerializer, partial=True)
        return Response(
            api_ok(
                "Updated Vietstock finance chart assessment successfully",
                sf.update_assessment(ticker, d.get("overviewAssessment")),
            )
        )
