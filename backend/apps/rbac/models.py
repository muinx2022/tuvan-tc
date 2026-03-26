from django.db import models
from django.db.models import CompositePrimaryKey


class Permission(models.Model):
    id = models.BigAutoField(primary_key=True)
    code = models.CharField(max_length=120, unique=True)
    description = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        managed = False
        db_table = "permissions"


class Role(models.Model):
    id = models.BigAutoField(primary_key=True)
    code = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=120)
    permissions = models.ManyToManyField(
        Permission,
        through="RolePermission",
        related_name="roles_m2m",
        blank=True,
    )

    class Meta:
        managed = False
        db_table = "roles"


class RolePermission(models.Model):
    role = models.ForeignKey(Role, models.CASCADE, db_column="role_id")
    permission = models.ForeignKey(Permission, models.CASCADE, db_column="permission_id")
    pk = CompositePrimaryKey("role", "permission")

    class Meta:
        managed = False
        db_table = "role_permissions"
