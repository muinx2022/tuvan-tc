from __future__ import annotations

from typing import Iterable


class AuthUser:
    """Mirrors Spring Security AuthUser + JWT claims."""

    is_authenticated = True

    def __init__(
        self,
        id: int,
        email: str,
        role: str,
        permissions: Iterable[str] | None = None,
    ):
        self.id = id
        self.email = email
        self.role = role
        self.permissions = set(permissions) if permissions else set()

    def has_authority(self, authority: str) -> bool:
        if self.role == "ROLE_ADMIN":
            return True
        if authority in self.permissions:
            return True
        return False
