from __future__ import annotations

import datetime as dt
from typing import Any

import jwt
from django.conf import settings


def generate_access_token(user_id: int, email: str, role: str, permissions: list[str]) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    exp = now + dt.timedelta(minutes=settings.APP_JWT_ACCESS_TOKEN_MINUTES)
    payload: dict[str, Any] = {
        "sub": email,
        "uid": user_id,
        "role": role,
        "permissions": sorted(permissions),
        "iat": now,
        "exp": exp,
    }
    return jwt.encode(payload, settings.APP_JWT_SECRET, algorithm="HS256")


def parse_access_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.APP_JWT_SECRET, algorithms=["HS256"])
