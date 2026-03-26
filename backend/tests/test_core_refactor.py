from __future__ import annotations

from django.test import SimpleTestCase
from django.urls import resolve
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.categories.views import CategoryTreeView
from apps.posts.views import PostListCreateView
from apps.stock_finance.views import FinanceChartSyncStatusView
from apps.users.services import get_me_permissions
from common.admin_api import AdminAPIView, AdminOnlyAPIView
from common.auth_user import AuthUser


class _PermissionMappedView(AdminAPIView):
    permission_map = {"GET": ("role.view",)}

    def get(self, request):
        return Response({"ok": True})


class _AdminOnlyView(AdminOnlyAPIView):
    def get(self, request):
        return Response({"ok": True})


class RoutingTests(SimpleTestCase):
    def test_posts_route_resolves_via_app_urls(self):
        match = resolve("/api/v1/admin/posts")
        self.assertIs(match.func.view_class, PostListCreateView)

    def test_category_tree_route_resolves_via_app_urls(self):
        match = resolve("/api/v1/admin/categories/tree")
        self.assertIs(match.func.view_class, CategoryTreeView)

    def test_finance_chart_status_route_resolves_via_app_urls(self):
        match = resolve("/api/v1/admin/stock-finance-charts/sync/status")
        self.assertIs(match.func.view_class, FinanceChartSyncStatusView)


class AdminApiPermissionTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def test_permission_mapped_view_denies_authenticated_user_without_permission(self):
        request = self.factory.get("/permission-mapped")
        force_authenticate(request, user=AuthUser(10, "viewer@example.com", "ROLE_AUTHENTICATED", []))
        response = _PermissionMappedView.as_view()(request)
        self.assertEqual(response.status_code, 403)

    def test_permission_mapped_view_allows_user_with_permission(self):
        request = self.factory.get("/permission-mapped")
        force_authenticate(request, user=AuthUser(10, "viewer@example.com", "ROLE_AUTHENTICATED", ["role.view"]))
        response = _PermissionMappedView.as_view()(request)
        self.assertEqual(response.status_code, 200)

    def test_admin_only_view_allows_role_admin(self):
        request = self.factory.get("/admin-only")
        force_authenticate(request, user=AuthUser(1, "admin@example.com", "ROLE_ADMIN", []))
        response = _AdminOnlyView.as_view()(request)
        self.assertEqual(response.status_code, 200)


class PermissionSemanticsTests(SimpleTestCase):
    def test_role_authenticated_keeps_authenticated_web_permission(self):
        auth_user = AuthUser(99, "member@example.com", "ROLE_AUTHENTICATED", [])
        self.assertEqual(get_me_permissions(auth_user), ["authenticated.web"])
