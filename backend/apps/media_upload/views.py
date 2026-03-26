from __future__ import annotations

from rest_framework.response import Response

from apps.settings_app import services as sett_services
from common.admin_api import AdminOnlyAPIView
from common.exceptions import BadRequestError
from common.response import api_error, api_ok


class MediaUploadView(AdminOnlyAPIView):

    def post(self, request):
        f = request.FILES.get("file")
        if not f:
            return Response(api_error("Upload file is required"), status=400)
        folder = request.POST.get("folder")
        try:
            data = sett_services.upload_media(f, folder)
            # camelCase keys for response
            return Response(
                api_ok(
                    "Uploaded media successfully",
                    {
                        "provider": data["provider"],
                        "assetType": data["assetType"],
                        "url": data["url"],
                        "publicId": data["publicId"],
                        "originalFilename": data["originalFilename"],
                        "contentType": data["contentType"],
                        "size": data["size"],
                    },
                )
            )
        except BadRequestError as e:
            return Response(api_error(str(e)), status=400)
