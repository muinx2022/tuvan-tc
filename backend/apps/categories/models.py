from django.db import models


class Category(models.Model):
    id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=120)
    slug = models.CharField(max_length=160, unique=True)
    parent = models.ForeignKey(
        "self",
        models.SET_NULL,
        null=True,
        blank=True,
        db_column="parent_id",
        related_name="children",
    )
    sort_order = models.IntegerField(db_column="sort_order")
    is_published = models.BooleanField(db_column="is_published")
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "categories"
