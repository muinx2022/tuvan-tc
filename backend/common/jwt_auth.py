from __future__ import annotations

import jwt
from django.contrib.auth.models import AnonymousUser
from rest_framework import authentication
from rest_framework.request import Request

from common.auth_user import AuthUser


class JWTAuthentication(authentication.BaseAuthentication):
    keyword = b"Bearer"

    def authenticate(self, request: Request):
        header = request.META.get("HTTP_AUTHORIZATION")
        if not header or not header.startswith("Bearer "):
            return None
        token = header[7:].strip()
        if not token:
            return None
        try:
            from common.jwt_service import parse_access_token

            claims = parse_access_token(token)
        except jwt.PyJWTError:
            return None

        uid = claims.get("uid")
        email = claims.get("sub")
        role = claims.get("role")
        perms = claims.get("permissions") or []
        if uid is None or email is None or role is None:
            return None
        user = AuthUser(int(uid), str(email), str(role), perms if isinstance(perms, list) else list(perms))
        return (user, None)


def get_current_user(request) -> AuthUser | AnonymousUser:
    user = getattr(request, "user", None)
    if user is None or isinstance(user, AnonymousUser):
        return AnonymousUser()
    return user
