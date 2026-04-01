from django.urls import path

from apps.stocks import views

urlpatterns = [
    path("admin/stocks", views.StockSymbolListView.as_view()),
    path("admin/stocks/sync", views.StockSyncView.as_view()),
    path("admin/stocks/sync/status", views.StockSyncStatusView.as_view()),
    path("admin/stocks/history/sync", views.StockHistorySyncView.as_view()),
    path("admin/stocks/history/sync/reset", views.StockHistorySyncResetView.as_view()),
    path("admin/stocks/history/sync/status", views.StockHistorySyncStatusView.as_view()),
    path("admin/stocks/<str:ticker>/history/resync", views.StockHistoryTickerResyncView.as_view()),
    path("admin/stocks/industry-groups", views.StockIndustryGroupsView.as_view()),
    path("admin/stocks/tickers", views.StockTickersView.as_view()),
    path("admin/stocks/analytics/industry", views.StockAnalyticsIndustryView.as_view()),
    path("admin/stocks/analytics/ticker", views.StockAnalyticsTickerView.as_view()),
    path("admin/stocks/analytics/industry-allocation", views.StockIndustryAllocationView.as_view()),
    path("admin/stocks/analytics/ticker-allocation", views.StockTickerAllocationView.as_view()),
    path("admin/stocks/t0-status", views.StockT0StatusView.as_view()),
    path("admin/stocks/t0-snapshots", views.StockT0SnapshotListView.as_view()),
    path("admin/stocks/t0-snapshot-slots", views.StockT0SnapshotSlotsView.as_view()),
    path("admin/stocks/t0-realtime", views.StockT0RealtimeListView.as_view()),
    path("admin/stocks/t0-snapshots/<str:ticker>", views.StockT0TickerTimelineView.as_view()),
    path("admin/stocks/money-flow-features", views.StockMoneyFlowFeatureListView.as_view()),
    path("admin/stocks/money-flow-features/rebuild", views.StockMoneyFlowFeatureRebuildView.as_view()),
    path("admin/stocks/money-flow-features/backfill-eod", views.StockMoneyFlowFeatureBackfillEodView.as_view()),
    path("admin/stocks/money-flow-features/backfill-slot", views.StockMoneyFlowFeatureBackfillSlotView.as_view()),
    path("admin/stocks/foreign-trading", views.StockForeignTradingListView.as_view()),
    path("admin/stocks/foreign-trading/<str:ticker>", views.StockForeignTradingTickerTimelineView.as_view()),
    path("admin/stocks/<str:ticker>/history", views.StockHistoryByTickerView.as_view()),
]
