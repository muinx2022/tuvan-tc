from __future__ import annotations

from rest_framework.response import Response

from apps.rbac import services as rbac_services
from apps.rbac.serializers import RoleWriteSerializer
from common.admin_api import AdminAPIView
from common.response import api_ok


class RbacPermissionsView(AdminAPIView):
    permission_map = {"GET": ("role.view",)}

    def get(self, request):
        return Response(api_ok("Fetched permissions successfully", rbac_services.list_permissions()))


class RbacRoleListCreateView(AdminAPIView):
    permission_map = {
        "GET": ("role.view",),
        "POST": ("role.create",),
    }

    def get(self, request):
        return Response(api_ok("Fetched roles successfully", rbac_services.list_roles()))

    def post(self, request):
        d = self.validate_body(RoleWriteSerializer)
        out = rbac_services.create_role(
            d["code"],
            d["name"],
            d.get("permissionIds", []),
        )
        return Response(api_ok("Role created successfully", out))


class RbacRoleDetailView(AdminAPIView):
    permission_map = {
        "PUT": ("role.update",),
        "DELETE": ("role.delete",),
    }

    def put(self, request, pk: int):
        d = self.validate_body(RoleWriteSerializer)
        out = rbac_services.update_role(
            pk,
            d["code"],
            d["name"],
            d.get("permissionIds", []),
        )
        return Response(api_ok("Role updated successfully", out))

    def delete(self, request, pk: int):
        rbac_services.delete_role(pk)
        return Response(api_ok("Role deleted successfully"))
