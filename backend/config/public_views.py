import mimetypes
from pathlib import Path

from django.http import FileResponse, Http404
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.settings_app.services import get_media_entity
from common.response import api_ok


class RootView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response(api_ok("Backend is running", {"service": "backend"}))


class PublicHealthView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response(api_ok("Service is healthy", {"status": "UP"}))


class PublicInfoView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response(api_ok("Backend is running", {"service": "backend"}))


def public_media_file(request, file_name: str):
    m = get_media_entity()
    root = Path(m.local_root_path or "uploads").resolve()
    target = (root / file_name).resolve()
    if not str(target).startswith(str(root)) or not target.is_file():
        raise Http404("Media file not found")
    ctype, _ = mimetypes.guess_type(str(target))
    fh = open(target, "rb")
    return FileResponse(fh, content_type=ctype or "application/octet-stream")
