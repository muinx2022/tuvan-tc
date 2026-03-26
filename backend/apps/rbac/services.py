from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.rbac.models import Permission, Role, RolePermission
from common.exceptions import NotFoundError

SYSTEM_ROLE_CODES = frozenset({"ROLE_ADMIN", "ROLE_AUTHENTICATED"})


def perm_summary(p: Permission) -> dict:
    return {"id": p.id, "code": p.code, "description": p.description}


def role_summary(role: Role) -> dict:
    perm_ids = RolePermission.objects.filter(role_id=role.id).values_list("permission_id", flat=True)
    perms = sorted(
        [perm_summary(p) for p in Permission.objects.filter(id__in=perm_ids)],
        key=lambda x: x["code"].lower(),
    )
    return {"id": role.id, "code": role.code, "name": role.name, "permissions": perms}


def list_permissions() -> list[dict]:
    return [perm_summary(p) for p in Permission.objects.order_by("code")]


def list_roles() -> list[dict]:
    return [role_summary(r) for r in Role.objects.order_by("code")]


@transaction.atomic
def create_role(code: str, name: str, permission_ids: list[int]) -> dict:
    code_n = _normalize_code(code)
    if Role.objects.filter(code=code_n).exists():
        raise ValueError("Role code already exists")
    perms = list(Permission.objects.filter(id__in=permission_ids))
    if len(perms) != len(set(permission_ids)):
        raise ValueError("One or more permissions do not exist")
    now = timezone.now()
    role = Role(code=code_n, name=name.strip())
    role.save(force_insert=True)
    for p in perms:
        RolePermission(role=role, permission=p).save()
    return role_summary(Role.objects.get(pk=role.id))


@transaction.atomic
def update_role(role_id: int, code: str, name: str, permission_ids: list[int]) -> dict:
    try:
        role = Role.objects.get(pk=role_id)
    except Role.DoesNotExist:
        raise NotFoundError("Role not found")
    if role.code in SYSTEM_ROLE_CODES:
        raise ValueError("System role cannot be modified")
    code_n = _normalize_code(code)
    if Role.objects.filter(code=code_n).exclude(pk=role_id).exists():
        raise ValueError("Role code already exists")
    perms = list(Permission.objects.filter(id__in=permission_ids))
    if len(perms) != len(set(permission_ids)):
        raise ValueError("One or more permissions do not exist")
    role.code = code_n
    role.name = name.strip()
    role.save()
    RolePermission.objects.filter(role_id=role.id).delete()
    for p in perms:
        RolePermission(role=role, permission=p).save()
    return role_summary(Role.objects.get(pk=role.id))


@transaction.atomic
def delete_role(role_id: int) -> None:
    try:
        role = Role.objects.get(pk=role_id)
    except Role.DoesNotExist:
        raise NotFoundError("Role not found")
    if role.code in SYSTEM_ROLE_CODES:
        raise ValueError("System role cannot be modified")
    role.delete()


def _normalize_code(code: str) -> str:
    c = code.strip().upper()
    return c if c.startswith("ROLE_") else "ROLE_" + c
