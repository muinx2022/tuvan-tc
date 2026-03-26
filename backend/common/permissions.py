from __future__ import annotations

from rest_framework.permissions import BasePermission

from common.auth_user import AuthUser


class IsAuthenticatedUser(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and getattr(request.user, "is_authenticated", False))


class IsAdminOrPermission(BasePermission):
    """Spring: hasAuthority('ROLE_ADMIN') or hasAuthority(perm)"""

    def __init__(self, *authorities: str):
        self.authorities = authorities

    def has_permission(self, request, view):
        user = request.user
        if not user or not getattr(user, "is_authenticated", False):
            return False
        if not isinstance(user, AuthUser):
            return False
        if user.role == "ROLE_ADMIN":
            return True
        for a in self.authorities:
            if a in user.permissions:
                return True
        return False


def require_admin_or(*perms: str):
    return IsAdminOrPermission(*perms)
