from __future__ import annotations

import re
import unicodedata

from django.db import models as m
from django.db import transaction
from django.utils import timezone

from apps.categories.models import Category
from common.exceptions import BadRequestError, NotFoundError


def _norm_slug(value: str) -> str:
    if not value or not str(value).strip():
        return ""
    ascii_str = unicodedata.normalize("NFD", value.strip().lower())
    ascii_str = "".join(c for c in ascii_str if unicodedata.category(c) != "Mn")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_str)
    return re.sub(r"^-+|-+$", "", slug)


def _unique_slug(name: str, self_id: int | None) -> str:
    base = _norm_slug(name)
    if not base:
        raise BadRequestError("Category name is invalid")
    candidate = base
    suffix = 2
    while True:
        q = Category.objects.filter(slug=candidate)
        if self_id is not None:
            q = q.exclude(pk=self_id)
        if not q.exists():
            return candidate
        candidate = f"{base}-{suffix}"
        suffix += 1


def category_dict(c: Category) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "slug": c.slug,
        "parentId": c.parent_id,
        "sortOrder": c.sort_order,
        "published": c.is_published,
        "createdAt": c.created_at.isoformat() if c.created_at else None,
        "updatedAt": c.updated_at.isoformat() if c.updated_at else None,
    }


def tree_dict(c: Category) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "slug": c.slug,
        "parentId": c.parent_id,
        "sortOrder": c.sort_order,
        "published": c.is_published,
        "children": [],
    }


def find_all() -> list[dict]:
    return [category_dict(c) for c in Category.objects.order_by("sort_order", "id")]


def find_tree() -> list[dict]:
    cats = list(Category.objects.order_by("sort_order", "id"))
    by_id = {c.id: tree_dict(c) for c in cats}
    roots: list[dict] = []
    for c in cats:
        node = by_id[c.id]
        pid = node["parentId"]
        if pid is None:
            roots.append(node)
        else:
            parent = by_id.get(pid)
            if parent is not None:
                parent["children"].append(node)
            else:
                roots.append(node)
    return roots


def find_one(cid: int) -> dict:
    try:
        return category_dict(Category.objects.get(pk=cid))
    except Category.DoesNotExist:
        raise NotFoundError("Category not found")


def _is_descendant(candidate_parent: Category, node: Category) -> bool:
    cur: Category | None = candidate_parent
    while cur is not None:
        if cur.id == node.id:
            return True
        cur = cur.parent
    return False


@transaction.atomic
def create_cat(name: str, parent_id: int | None) -> dict:
    slug = _unique_slug(name, None)
    parent = Category.objects.filter(pk=parent_id).first() if parent_id else None
    if parent_id and not parent:
        raise BadRequestError("Parent category not found")
    max_so = Category.objects.filter(parent_id=parent_id).aggregate(mx=m.Max("sort_order"))["mx"] or 0
    now = timezone.now()
    c = Category(
        name=name.strip(),
        slug=slug,
        parent=parent,
        sort_order=max_so + 1,
        is_published=True,
        created_at=now,
        updated_at=now,
    )
    c.save(force_insert=True)
    return category_dict(c)


@transaction.atomic
def update_cat(cid: int, name: str, parent_id: int | None) -> dict:
    try:
        cat = Category.objects.get(pk=cid)
    except Category.DoesNotExist:
        raise NotFoundError("Category not found")
    if parent_id is not None and parent_id == cid:
        raise BadRequestError("Category cannot be parent of itself")
    new_parent = Category.objects.filter(pk=parent_id).first() if parent_id else None
    if parent_id and not new_parent:
        raise BadRequestError("Parent category not found")
    if new_parent and _is_descendant(new_parent, cat):
        raise BadRequestError("Category parent is invalid")
    slug = _unique_slug(name, cid)
    old_parent_id = cat.parent_id
    cat.name = name.strip()
    cat.slug = slug
    cat.parent = new_parent
    if old_parent_id != parent_id:
        max_so = Category.objects.filter(parent_id=parent_id).aggregate(mx=m.Max("sort_order"))["mx"] or 0
        cat.sort_order = max_so + 1
    cat.updated_at = timezone.now()
    cat.save()
    return category_dict(cat)


@transaction.atomic
def reorder(items: list[dict]) -> None:
    if not items:
        return
    ids = [int(x["id"]) for x in items]
    if len(ids) != len(set(ids)):
        raise BadRequestError("Duplicate category ids in reorder payload")
    by_id = {c.id: c for c in Category.objects.filter(id__in=ids)}
    if len(by_id) != len(ids):
        raise BadRequestError("One or more categories not found")
    for it in items:
        c = by_id[int(it["id"])]
        pid = it.get("parentId")
        parent = Category.objects.filter(pk=pid).first() if pid else None
        if pid and not parent:
            raise BadRequestError(f"Parent category not found: {pid}")
        if pid and (int(it["id"]) == pid or (parent and _is_descendant(parent, c))):
            raise BadRequestError("Category parent is invalid")
        c.parent = parent
        c.sort_order = int(it["sortOrder"])
        c.updated_at = timezone.now()
        c.save()


@transaction.atomic
def delete_subtree(cid: int) -> None:
    for ch in Category.objects.filter(parent_id=cid):
        delete_subtree(ch.id)
    Category.objects.filter(pk=cid).delete()


def delete_cat(cid: int) -> None:
    try:
        Category.objects.get(pk=cid)
    except Category.DoesNotExist:
        raise NotFoundError("Category not found")
    delete_subtree(cid)


@transaction.atomic
def update_publish(cid: int, published: bool) -> dict:
    try:
        c = Category.objects.get(pk=cid)
    except Category.DoesNotExist:
        raise NotFoundError("Category not found")
    c.is_published = published
    c.updated_at = timezone.now()
    c.save()
    return category_dict(c)
