from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.rbac.models import Role
from apps.users.models import User, UserRole
from common.auth_user import AuthUser
from common.exceptions import ForbiddenError, NotFoundError
from common.pwhash import hash_password


def user_to_summary(user: User) -> dict:
    rbac = []
    for ur in UserRole.objects.filter(user_id=user.id).select_related("role"):
        r = ur.role
        rbac.append({"id": r.id, "code": r.code, "name": r.name})
    rbac.sort(key=lambda x: x["code"].lower())
    return {
        "id": user.id,
        "fullName": user.full_name,
        "email": user.email,
        "role": user.role,
        "rbacRoles": rbac,
    }


def get_me_permissions(auth: AuthUser) -> list[str]:
    if auth.permissions:
        return sorted(auth.permissions)
    if auth.role == "ROLE_ADMIN":
        return sorted(["*", "admin.portal.access"])
    return ["authenticated.web"]


def get_user_or_404(user_id: int) -> User:
    try:
        return User.objects.get(pk=user_id)
    except User.DoesNotExist:
        raise NotFoundError("User not found")


@transaction.atomic
def create_user(full_name: str, email: str, password: str, role: str, role_ids: list[int] | None) -> dict:
    email_n = email.lower().strip()
    if User.objects.filter(email=email_n).exists():
        raise ValueError("Email already exists")
    now = timezone.now()
    user = User(
        full_name=full_name.strip(),
        email=email_n,
        password=hash_password(password),
        role=role,
        created_at=now,
        updated_at=now,
    )
    user.save(force_insert=True)
    apply_rbac_roles(user, role_ids)
    user.refresh_from_db()
    return user_to_summary(user)


def apply_rbac_roles(user: User, role_ids: list[int] | None) -> None:
    if role_ids is None:
        return
    unique_ids = list(dict.fromkeys(role_ids))
    roles = list(Role.objects.filter(id__in=unique_ids))
    if len(roles) != len(unique_ids):
        raise ValueError("One or more RBAC roles do not exist")
    UserRole.objects.filter(user_id=user.id).delete()
    for r in roles:
        UserRole(user=user, role=r).save()


@transaction.atomic
def update_user(
    user_id: int,
    full_name: str,
    email: str,
    password: str | None,
    role: str,
    role_ids: list[int] | None,
    actor: AuthUser,
) -> dict:
    user = get_user_or_404(user_id)
    email_n = email.lower().strip()
    if User.objects.filter(email=email_n).exclude(pk=user_id).exists():
        raise ValueError("Email already exists")
    if user.role == "ROLE_ADMIN" and role != "ROLE_ADMIN":
        ensure_not_last_admin(user_id)
    user.full_name = full_name.strip()
    user.email = email_n
    user.role = role
    if password and len(password) >= 6:
        user.password = hash_password(password)
    user.updated_at = timezone.now()
    user.save()
    apply_rbac_roles(user, role_ids)
    user.refresh_from_db()
    return user_to_summary(user)


@transaction.atomic
def update_role_only(user_id: int, role: str) -> dict:
    user = get_user_or_404(user_id)
    if user.role == "ROLE_ADMIN" and role != "ROLE_ADMIN":
        ensure_not_last_admin(user_id)
    user.role = role
    user.updated_at = timezone.now()
    user.save(update_fields=["role", "updated_at"])
    return user_to_summary(user)


@transaction.atomic
def update_rbac_only(user_id: int, role_ids: list[int] | None) -> dict:
    user = get_user_or_404(user_id)
    apply_rbac_roles(user, role_ids)
    user.refresh_from_db()
    return user_to_summary(user)


def ensure_not_last_admin(target_user_id: int) -> None:
    total = User.objects.filter(role="ROLE_ADMIN").count()
    if total <= 1:
        u = User.objects.get(pk=target_user_id)
        if u.role == "ROLE_ADMIN":
            raise ValueError("Cannot remove the last admin user")


@transaction.atomic
def delete_user(user_id: int, actor: AuthUser) -> None:
    user = get_user_or_404(user_id)
    if actor.id == user_id and user.role == "ROLE_ADMIN":
        raise ValueError("Cannot delete your own admin account")
    if user.role == "ROLE_ADMIN":
        ensure_not_last_admin(user_id)
    user.delete()
