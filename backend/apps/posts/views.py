from __future__ import annotations

from rest_framework.response import Response

from apps.posts import services as post_services
from apps.posts.serializers import PostWriteSerializer
from common.admin_api import AdminOnlyAPIView
from common.jwt_auth import get_current_user
from common.response import api_ok


class PostListCreateView(AdminOnlyAPIView):
    def get(self, request):
        return Response(api_ok("Fetched posts successfully", post_services.find_all()))

    def post(self, request):
        from common.auth_user import AuthUser

        u = get_current_user(request)
        d = self.validate_body(PostWriteSerializer)
        out = post_services.create_post(
            d["title"],
            d.get("content"),
            d.get("published", False),
            d.get("categoryIds", []),
            d.get("authorId"),
            u.id if isinstance(u, AuthUser) else 0,
        )
        return Response(api_ok("Post created successfully", out))


class PostDetailView(AdminOnlyAPIView):
    def get(self, request, pk: int):
        return Response(api_ok("Fetched post successfully", post_services.find_one(pk)))

    def put(self, request, pk: int):
        from common.auth_user import AuthUser

        u = get_current_user(request)
        d = self.validate_body(PostWriteSerializer)
        out = post_services.update_post(
            pk,
            d["title"],
            d.get("content"),
            d.get("published", False),
            d.get("categoryIds", []),
            d.get("authorId"),
            u.id if isinstance(u, AuthUser) else 0,
        )
        return Response(api_ok("Post updated successfully", out))

    def delete(self, request, pk: int):
        post_services.delete_post(pk)
        return Response(api_ok("Post deleted successfully"))
