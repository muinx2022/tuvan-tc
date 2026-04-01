from django.urls import path

from apps.settings_app import views

urlpatterns = [
    path("public/settings/google-oauth", views.PublicGoogleOauthConfigView.as_view()),
    path("admin/settings/media", views.MediaSettingView.as_view()),
    path("admin/settings/dnse", views.DnseSettingView.as_view()),
    path("admin/settings/ssi-fc", views.SsiFcSettingView.as_view()),
    path("admin/settings/google-oauth", views.GoogleOauthSettingView.as_view()),
    path("admin/settings/history-sync-schedule", views.HistorySyncScheduleSettingView.as_view()),
    path("admin/settings/t0-snapshot-schedule", views.T0SnapshotScheduleSettingView.as_view()),
    path("admin/settings/money-flow-features", views.MoneyFlowFeatureSettingView.as_view()),
]
