from __future__ import annotations

from common.auth_user import AuthUser


def is_role_admin(user) -> bool:
    return isinstance(user, AuthUser) and user.role == "ROLE_ADMIN"


def require_admin_only(user) -> bool:
    """Endpoints annotated with @PreAuthorize("hasAuthority('ROLE_ADMIN')") only."""
    return isinstance(user, AuthUser) and user.role == "ROLE_ADMIN"


def require_admin_or_any_permission(user, *perms: str) -> bool:
    """Spring: hasAuthority('ROLE_ADMIN') or hasAuthority('perm')."""
    if not isinstance(user, AuthUser):
        return False
    if user.role == "ROLE_ADMIN":
        return True
    return any(p in user.permissions for p in perms)
