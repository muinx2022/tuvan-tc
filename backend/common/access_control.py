from __future__ import annotations

from apps.rbac.models import Permission, RolePermission
from apps.users.models import User, UserRole


def resolve_permissions(user: User) -> set[str]:
    permissions: set[str] = set()
    if user.role == "ROLE_ADMIN":
        permissions.add("*")
        permissions.add("admin.portal.access")
    if user.role in {"ROLE_USER", "ROLE_AUTHENTICATED"}:
        permissions.add("authenticated.web")

    role_ids = UserRole.objects.filter(user_id=user.id).values_list("role_id", flat=True)
    from apps.rbac.models import RolePermission

    perm_ids = (
        RolePermission.objects.filter(role_id__in=role_ids)
        .values_list("permission_id", flat=True)
        .distinct()
    )

    for code in Permission.objects.filter(id__in=perm_ids).values_list("code", flat=True):
        permissions.add(code)
    return permissions
