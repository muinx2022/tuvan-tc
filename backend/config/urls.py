from django.urls import include, path

from config.public_views import (
    PublicHealthView,
    PublicInfoView,
    RootView,
    public_media_file,
)

urlpatterns = [
    path("", RootView.as_view()),
    path("api/v1/public/health", PublicHealthView.as_view()),
    path("api/v1/public/", PublicInfoView.as_view()),
    path("api/v1/public/media/<path:file_name>", public_media_file),
    path("api/v1/auth/", include("apps.authentication.urls")),
    path("api/v1/", include("apps.users.api_urls")),
    path("api/v1/", include("apps.rbac.urls")),
    path("api/v1/", include("apps.stocks.urls")),
    path("api/v1/", include("apps.stock_finance.urls")),
    path("api/v1/", include("apps.categories.urls")),
    path("api/v1/", include("apps.posts.urls")),
    path("api/v1/", include("apps.media_upload.urls")),
    path("api/v1/", include("apps.settings_app.urls")),
    path("api/v1/products", include("apps.products.urls")),
]
