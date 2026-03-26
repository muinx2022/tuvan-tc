from django.db import models
from django.db.models import CompositePrimaryKey

from apps.categories.models import Category
from apps.users.models import User


class Post(models.Model):
    id = models.BigAutoField(primary_key=True)
    title = models.CharField(max_length=200)
    slug = models.CharField(max_length=180, unique=True)
    content = models.TextField(null=True, blank=True)
    published = models.BooleanField()
    author = models.ForeignKey(User, models.CASCADE, db_column="author_id", related_name="posts")
    categories = models.ManyToManyField(
        Category,
        through="PostCategory",
        related_name="posts_m2m",
        blank=True,
    )
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "posts"


class PostCategory(models.Model):
    post = models.ForeignKey(Post, models.CASCADE, db_column="post_id")
    category = models.ForeignKey(Category, models.CASCADE, db_column="category_id")
    pk = CompositePrimaryKey("post", "category")

    class Meta:
        managed = False
        db_table = "post_categories"
