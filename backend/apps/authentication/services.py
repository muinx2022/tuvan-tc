from __future__ import annotations

import uuid
from datetime import timedelta

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.users.models import PasswordResetToken, RefreshToken, User
from common.access_control import resolve_permissions
from common.jwt_service import generate_access_token
from common.pwhash import hash_password, verify_password


def _normalize_datetime(value):
    if value is None:
        return None
    if timezone.is_naive(value):
        return timezone.make_aware(value, timezone.get_current_timezone())
    return value


def _is_expired(expires_at) -> bool:
    normalized = _normalize_datetime(expires_at)
    if normalized is None:
        return True
    return normalized < timezone.now()


def _auth_response_dict(user: User, access: str, refresh: str) -> dict:
    perms = sorted(resolve_permissions(user))
    return {
        "accessToken": access,
        "refreshToken": refresh,
        "userId": user.id,
        "fullName": user.full_name,
        "email": user.email,
        "role": user.role,
        "permissions": perms,
    }


@transaction.atomic
def build_tokens(user: User) -> dict:
    perms = sorted(resolve_permissions(user))
    access = generate_access_token(user.id, user.email, user.role, perms)
    rt = RefreshToken(
        user=user,
        token=str(uuid.uuid4()),
        expires_at=timezone.now() + timedelta(days=settings.APP_JWT_REFRESH_TOKEN_DAYS),
        revoked=False,
        created_at=timezone.now(),
    )
    rt.save(force_insert=True)
    return _auth_response_dict(user, access, rt.token)


def verify_google_token(id_token: str) -> tuple[str, str, str | None]:
    from apps.settings_app.services import get_google_oauth_runtime_config

    oauth_cfg = get_google_oauth_runtime_config()
    client_id = (oauth_cfg.get("clientId") or "").strip()
    if not client_id:
        raise ValueError("Google sign-in is not configured")
    r = requests.get(
        "https://oauth2.googleapis.com/tokeninfo",
        params={"id_token": id_token},
        timeout=30,
    )
    if r.status_code != 200:
        raise ValueError("Google token is invalid")
    body = r.json()
    sub = body.get("sub")
    email = body.get("email")
    if not sub or not email:
        raise ValueError("Google token is invalid")
    if body.get("aud") != client_id:
        raise ValueError("Google token audience is invalid")
    if str(body.get("email_verified", "")).lower() != "true":
        raise ValueError("Google account email is not verified")
    name = body.get("name")
    return sub, email.lower().strip(), name


@transaction.atomic
def register_user(full_name: str, email: str, password: str) -> dict:
    email_n = email.lower().strip()
    if User.objects.filter(email=email_n).exists():
        raise ValueError("Email already exists")
    now = timezone.now()
    user = User(
        full_name=full_name.strip(),
        email=email_n,
        password=hash_password(password),
        role="ROLE_AUTHENTICATED",
        created_at=now,
        updated_at=now,
    )
    user.save(force_insert=True)
    return build_tokens(user)


@transaction.atomic
def login_user(email: str, password: str) -> dict:
    email_n = email.lower().strip()
    try:
        user = User.objects.get(email=email_n)
    except User.DoesNotExist:
        raise ValueError("Invalid credentials")
    if not verify_password(password, user.password):
        raise ValueError("Invalid credentials")
    return build_tokens(user)


@transaction.atomic
def google_login(id_token: str) -> dict:
    sub, email, name = verify_google_token(id_token)
    user = User.objects.filter(google_sub=sub).first()
    if user is None:
        user = User.objects.filter(email=email).first()
        if user:
            if user.google_sub and user.google_sub != sub:
                raise ValueError("Google account is already linked to another profile")
            user.google_sub = sub
            if name and name.strip() and user.full_name != name.strip():
                user.full_name = name.strip()
            user.email = email
            user.updated_at = timezone.now()
            user.save(update_fields=["google_sub", "full_name", "email", "updated_at"])
        else:
            now = timezone.now()
            local = email.split("@")[0]
            user = User(
                full_name=name.strip() if name and name.strip() else local,
                email=email,
                google_sub=sub,
                password=hash_password(str(uuid.uuid4())),
                role="ROLE_AUTHENTICATED",
                created_at=now,
                updated_at=now,
            )
            user.save(force_insert=True)
    return build_tokens(user)


@transaction.atomic
def forgot_password(email: str) -> dict:
    email_n = email.lower().strip()
    user = User.objects.filter(email=email_n).first()
    if not user:
        return {"email": email_n, "resetToken": None, "expiresAt": None, "tokenExposed": False}
    PasswordResetToken.objects.filter(user=user).delete()
    tok = PasswordResetToken(
        user=user,
        token=str(uuid.uuid4()),
        expires_at=timezone.now() + timedelta(minutes=settings.APP_AUTH_PASSWORD_RESET_MINUTES),
        consumed=False,
        created_at=timezone.now(),
    )
    tok.save(force_insert=True)
    expose = settings.APP_AUTH_PASSWORD_RESET_EXPOSE_TOKEN
    return {
        "email": email_n,
        "resetToken": tok.token if expose else None,
        "expiresAt": tok.expires_at,
        "tokenExposed": expose,
    }


@transaction.atomic
def reset_password(token: str, new_password: str) -> None:
    try:
        pr = PasswordResetToken.objects.get(token=token)
    except PasswordResetToken.DoesNotExist:
        raise ValueError("Reset token is invalid")
    if pr.consumed or _is_expired(pr.expires_at):
        raise ValueError("Reset token is expired")
    u = pr.user
    u.password = hash_password(new_password)
    u.updated_at = timezone.now()
    u.save(update_fields=["password", "updated_at"])
    pr.consumed = True
    pr.save(update_fields=["consumed"])


@transaction.atomic
def refresh_tokens(refresh_token: str) -> dict:
    try:
        rt = RefreshToken.objects.get(token=refresh_token)
    except RefreshToken.DoesNotExist:
        raise ValueError("Refresh token is invalid")
    if rt.revoked or _is_expired(rt.expires_at):
        raise ValueError("Refresh token is expired")
    rt.revoked = True
    rt.save(update_fields=["revoked"])
    return build_tokens(rt.user)
