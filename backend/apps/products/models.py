from django.db import models

from apps.users.models import User


class Product(models.Model):
    id = models.BigAutoField(primary_key=True)
    owner = models.ForeignKey(User, models.CASCADE, db_column="owner_id", related_name="products")
    name = models.CharField(max_length=150)
    description = models.TextField(null=True, blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "products"
