from django.urls import path

from apps.stock_finance import views

urlpatterns = [
    path("admin/stock-finance-charts/sync/start", views.FinanceChartSyncStartView.as_view()),
    path("admin/stock-finance-charts/sync/status", views.FinanceChartSyncStatusView.as_view()),
    path("admin/stock-finance-charts/tickers", views.FinanceChartTickerListView.as_view()),
    path("admin/stock-finance-charts/<str:ticker>/assessment", views.FinanceChartAssessmentView.as_view()),
    path("admin/stock-finance-charts/<str:ticker>", views.FinanceChartByTickerView.as_view()),
]
