from django.db import models
from django.db.models import CompositePrimaryKey

from apps.rbac.models import Role


class User(models.Model):
    id = models.BigAutoField(primary_key=True)
    full_name = models.CharField(max_length=120, db_column="full_name")
    email = models.CharField(max_length=160, unique=True)
    google_sub = models.CharField(max_length=255, null=True, blank=True, unique=True)
    password = models.CharField(max_length=255)
    role = models.CharField(max_length=32)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()
    roles = models.ManyToManyField(
        Role,
        through="UserRole",
        related_name="users_m2m",
        blank=True,
    )

    class Meta:
        managed = False
        db_table = "users"


class UserRole(models.Model):
    user = models.ForeignKey(User, models.CASCADE, db_column="user_id")
    role = models.ForeignKey(Role, models.CASCADE, db_column="role_id")
    pk = CompositePrimaryKey("user", "role")

    class Meta:
        managed = False
        db_table = "user_roles"


class RefreshToken(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(User, models.CASCADE, db_column="user_id", related_name="refresh_tokens")
    token = models.CharField(max_length=255, unique=True)
    expires_at = models.DateTimeField()
    revoked = models.BooleanField(default=False)
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "refresh_tokens"


class PasswordResetToken(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(User, models.CASCADE, db_column="user_id", related_name="password_reset_tokens")
    token = models.CharField(max_length=255, unique=True)
    expires_at = models.DateTimeField()
    consumed = models.BooleanField(default=False)
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "password_reset_tokens"
