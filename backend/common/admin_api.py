from __future__ import annotations

from typing import Any

from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from common.authorization import require_admin_only, require_admin_or_any_permission
from common.jwt_auth import get_current_user


class AdminAPIView(APIView):
    permission_classes = [IsAuthenticated]
    admin_only_methods: set[str] = set()
    permission_map: dict[str, tuple[str, ...]] = {}

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        user = get_current_user(request)
        method = request.method.upper()
        if method in self.admin_only_methods:
            if not require_admin_only(user):
                raise PermissionDenied("Forbidden")
            return

        permissions = self.permission_map.get(method, ())
        if permissions and not require_admin_or_any_permission(user, *permissions):
            raise PermissionDenied("Forbidden")

    def validate_query(self, serializer_class, *, partial: bool = False):
        serializer = serializer_class(data=self.request.query_params, partial=partial)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data

    def validate_body(self, serializer_class, *, partial: bool = False):
        serializer = serializer_class(data=self.request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data


class AdminOnlyAPIView(AdminAPIView):
    admin_only_methods = {"GET", "POST", "PUT", "PATCH", "DELETE"}
