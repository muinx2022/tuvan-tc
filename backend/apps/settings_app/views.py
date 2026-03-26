from __future__ import annotations

from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.settings_app import services as sett_services
from apps.settings_app.serializers import (
    DnseSettingWriteSerializer,
    GoogleOauthSettingWriteSerializer,
    HistorySyncScheduleWriteSerializer,
    MediaSettingWriteSerializer,
    SsiFcSettingWriteSerializer,
    T0SnapshotScheduleWriteSerializer,
)
from common.admin_api import AdminAPIView
from common.response import api_ok


class MediaSettingView(AdminAPIView):
    permission_map = {
        "GET": ("settings.view",),
        "PUT": ("settings.update",),
    }

    def get(self, request):
        return Response(api_ok("Fetched media settings", sett_services.media_to_dict(sett_services.get_media_entity())))

    def put(self, request):
        data = self.validate_body(MediaSettingWriteSerializer)
        return Response(api_ok("Media settings saved", sett_services.save_media(data)))


class DnseSettingView(AdminAPIView):
    permission_map = {
        "GET": ("settings.view",),
        "PUT": ("settings.update",),
    }

    def get(self, request):
        return Response(api_ok("Fetched DNSE settings", sett_services.dnse_to_dict(sett_services.get_dnse_entity())))

    def put(self, request):
        data = self.validate_body(DnseSettingWriteSerializer)
        return Response(api_ok("DNSE settings saved", sett_services.save_dnse(data)))


class SsiFcSettingView(AdminAPIView):
    permission_map = {
        "GET": ("settings.view",),
        "PUT": ("settings.update",),
    }

    def get(self, request):
        return Response(api_ok("Fetched SSI FC settings", sett_services.get_ssi_fc_config()))

    def put(self, request):
        data = self.validate_body(SsiFcSettingWriteSerializer)
        return Response(api_ok("SSI FC settings saved", sett_services.save_ssi_fc(data)))


class GoogleOauthSettingView(AdminAPIView):
    permission_map = {
        "GET": ("settings.view",),
        "PUT": ("settings.update",),
    }

    def get(self, request):
        return Response(api_ok("Fetched Google OAuth settings", sett_services.get_google_oauth_config()))

    def put(self, request):
        data = self.validate_body(GoogleOauthSettingWriteSerializer)
        return Response(api_ok("Google OAuth settings saved", sett_services.save_google_oauth(data)))


class HistorySyncScheduleSettingView(AdminAPIView):
    permission_map = {
        "GET": ("settings.view",),
        "PUT": ("settings.update",),
    }

    def get(self, request):
        return Response(api_ok("Fetched history sync schedule settings", sett_services.get_history_sync_schedule_settings()))

    def put(self, request):
        data = self.validate_body(HistorySyncScheduleWriteSerializer)
        return Response(api_ok("History sync schedule settings saved", sett_services.save_history_sync_schedule(data)))


class T0SnapshotScheduleSettingView(AdminAPIView):
    permission_map = {
        "GET": ("settings.view",),
        "PUT": ("settings.update",),
    }

    def get(self, request):
        return Response(api_ok("Fetched T0 snapshot schedule settings", sett_services.get_t0_snapshot_schedule_config()))

    def put(self, request):
        data = self.validate_body(T0SnapshotScheduleWriteSerializer)
        return Response(api_ok("T0 snapshot schedule settings saved", sett_services.save_t0_snapshot_schedule(data)))


class PublicGoogleOauthConfigView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        runtime = sett_services.get_google_oauth_runtime_config()
        return Response(
            api_ok(
                "Fetched Google OAuth public config",
                {
                    "enabled": bool(runtime.get("enabled")),
                    "clientId": runtime.get("clientId") or "",
                },
            )
        )
