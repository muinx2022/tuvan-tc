from __future__ import annotations

import re
import unicodedata

from django.db import transaction
from django.utils import timezone

from apps.categories.models import Category
from apps.posts.models import Post, PostCategory
from apps.users.models import User
from common.exceptions import BadRequestError, NotFoundError


def _norm_slug(value: str) -> str:
    if not value or not str(value).strip():
        return ""
    ascii_str = unicodedata.normalize("NFD", value.strip().lower())
    ascii_str = "".join(c for c in ascii_str if unicodedata.category(c) != "Mn")
    return re.sub(r"^-+|-+$", "", re.sub(r"[^a-z0-9]+", "-", ascii_str))


def _unique_post_slug(title: str, self_id: int | None) -> str:
    base = _norm_slug(title)
    if not base:
        raise BadRequestError("Post title is invalid")
    candidate = base
    suffix = 2
    while True:
        q = Post.objects.filter(slug=candidate)
        if self_id is not None:
            q = q.exclude(pk=self_id)
        if not q.exists():
            return candidate
        candidate = f"{base}-{suffix}"
        suffix += 1


def post_dict(p: Post) -> dict:
    cats = [
        {"id": c.id, "name": c.name, "slug": c.slug}
        for c in p.categories.all()
    ]
    return {
        "id": p.id,
        "title": p.title,
        "slug": p.slug,
        "content": p.content,
        "published": p.published,
        "authorId": p.author_id,
        "authorName": p.author.full_name,
        "categoryIds": [c["id"] for c in cats],
        "categories": cats,
        "createdAt": p.created_at.isoformat() if p.created_at else None,
        "updatedAt": p.updated_at.isoformat() if p.updated_at else None,
    }


def find_all() -> list[dict]:
    return [post_dict(p) for p in Post.objects.select_related("author").prefetch_related("categories").order_by("-created_at")]


def find_one(pid: int) -> dict:
    try:
        p = Post.objects.select_related("author").prefetch_related("categories").get(pk=pid)
        return post_dict(p)
    except Post.DoesNotExist:
        raise NotFoundError("Post not found")


def _resolve_categories(ids: list[int] | None) -> list[Category]:
    if not ids:
        return []
    cats = list(Category.objects.filter(id__in=ids))
    found = {c.id for c in cats}
    missing = [i for i in ids if i not in found]
    if missing:
        raise BadRequestError(f"Categories not found: {missing}")
    return cats


@transaction.atomic
def create_post(title: str, content: str | None, published: bool, category_ids: list[int] | None, author_id: int | None, actor_id: int) -> dict:
    slug = _unique_post_slug(title, None)
    aid = author_id if author_id is not None else actor_id
    author = User.objects.filter(pk=aid).first()
    if author is None:
        raise BadRequestError("Author not found")
    now = timezone.now()
    p = Post(
        title=title.strip(),
        slug=slug,
        content=content,
        published=published,
        author=author,
        created_at=now,
        updated_at=now,
    )
    p.save(force_insert=True)
    for c in _resolve_categories(category_ids):
        PostCategory(post=p, category=c).save()
    p = Post.objects.select_related("author").prefetch_related("categories").get(pk=p.id)
    return post_dict(p)


@transaction.atomic
def update_post(pid: int, title: str, content: str | None, published: bool, category_ids: list[int] | None, author_id: int | None, actor_id: int) -> dict:
    try:
        p = Post.objects.get(pk=pid)
    except Post.DoesNotExist:
        raise NotFoundError("Post not found")
    slug = _unique_post_slug(title, pid)
    aid = author_id if author_id is not None else actor_id
    author = User.objects.filter(pk=aid).first()
    if author is None:
        raise BadRequestError("Author not found")
    p.title = title.strip()
    p.slug = slug
    p.content = content
    p.published = published
    p.author = author
    p.updated_at = timezone.now()
    p.save()
    PostCategory.objects.filter(post_id=p.id).delete()
    for c in _resolve_categories(category_ids):
        PostCategory(post=p, category=c).save()
    p = Post.objects.select_related("author").prefetch_related("categories").get(pk=p.id)
    return post_dict(p)


def delete_post(pid: int) -> None:
    try:
        Post.objects.get(pk=pid).delete()
    except Post.DoesNotExist:
        raise NotFoundError("Post not found")
