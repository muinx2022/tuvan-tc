from __future__ import annotations

from rest_framework.response import Response

from apps.users import services as user_services
from common.auth_user import AuthUser
from common.admin_api import AdminAPIView
from common.jwt_auth import get_current_user
from common.response import api_error, api_ok
from apps.users.serializers import (
    UserCreateSerializer,
    UserRbacPatchSerializer,
    UserRolePatchSerializer,
    UserUpdateSerializer,
)


class UserMeView(AdminAPIView):
    permission_map = {}

    def get(self, request):
        u = get_current_user(request)
        if not isinstance(u, AuthUser):
            return Response(api_error("Unauthorized"), status=401)
        try:
            from apps.users.models import User

            user = User.objects.get(pk=u.id)
            return Response(api_ok("Fetched profile successfully", user_services.user_to_summary(user)))
        except User.DoesNotExist:
            return Response(api_error("User not found"), status=404)


class AdminMePermissionsView(AdminAPIView):
    permission_map = {}

    def get(self, request):
        u = get_current_user(request)
        if not isinstance(u, AuthUser):
            return Response(api_error("Unauthorized"), status=401)
        return Response(
            api_ok(
                "Fetched permissions successfully",
                {"permissions": user_services.get_me_permissions(u)},
            )
        )


class AdminUserListView(AdminAPIView):
    permission_map = {
        "GET": ("user.view",),
        "POST": ("user.create",),
    }

    def get(self, request):
        from apps.users.models import User

        data = [user_services.user_to_summary(x) for x in User.objects.order_by("id")]
        return Response(api_ok("Fetched users successfully", data))

    def post(self, request):
        d = self.validate_body(UserCreateSerializer)
        out = user_services.create_user(
            d["fullName"],
            d["email"],
            d.get("password") or "",
            d.get("role", "ROLE_AUTHENTICATED"),
            d.get("roleIds", []),
        )
        return Response(api_ok("User created successfully", out))


class AdminUserDetailView(AdminAPIView):
    permission_map = {
        "GET": ("user.view",),
        "PUT": ("user.update",),
        "DELETE": ("user.delete",),
    }

    def get(self, request, pk: int):
        return Response(api_ok("Fetched user successfully", user_services.user_to_summary(user_services.get_user_or_404(pk))))

    def put(self, request, pk: int):
        u = get_current_user(request)
        d = self.validate_body(UserUpdateSerializer)
        pwd = d.get("password")
        if pwd == "":
            pwd = None
        out = user_services.update_user(
            pk,
            d.get("fullName") or "",
            d.get("email") or "",
            pwd,
            d.get("role") or "ROLE_AUTHENTICATED",
            d.get("roleIds", []),
            u,
        )
        return Response(api_ok("User updated successfully", out))

    def delete(self, request, pk: int):
        u = get_current_user(request)
        user_services.delete_user(pk, u)
        return Response(api_ok("User deleted successfully"))


class AdminUserPatchRoleView(AdminAPIView):
    permission_map = {"PATCH": ("user.update",)}

    def patch(self, request, pk: int):
        d = self.validate_body(UserRolePatchSerializer)
        out = user_services.update_role_only(pk, d["role"])
        return Response(api_ok("Role updated successfully", out))


class AdminUserPatchRbacView(AdminAPIView):
    permission_map = {"PATCH": ("user.update",)}

    def patch(self, request, pk: int):
        d = self.validate_body(UserRbacPatchSerializer)
        out = user_services.update_rbac_only(pk, d.get("roleIds", []))
        return Response(api_ok("RBAC roles updated successfully", out))


