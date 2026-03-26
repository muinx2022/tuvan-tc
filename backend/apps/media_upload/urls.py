from django.urls import path

from apps.media_upload.views import MediaUploadView

urlpatterns = [
    path("admin/media/upload", MediaUploadView.as_view()),
]
