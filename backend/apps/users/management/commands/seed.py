from django.core.management.base import BaseCommand
from django.db import connection, transaction
from django.utils import timezone

from apps.rbac.models import Permission, Role, RolePermission
from apps.users.models import User
from common.pwhash import hash_password
from django.conf import settings


class Command(BaseCommand):
    help = "Seed admin user, permissions, and RBAC roles (Flyway/RbacSeedConfig parity)."

    def handle(self, *args, **options):
        self.stdout.write("Seeding...")
        now = timezone.now()
        with transaction.atomic():
            perm_map = {
                "admin.portal.access": "Allow login to admin portal",
                "user.view": "View users",
                "user.create": "Create users",
                "user.update": "Update users",
                "user.delete": "Delete users",
                "role.view": "View roles",
                "role.create": "Create roles",
                "role.update": "Update roles",
                "role.delete": "Delete roles",
                "post.view": "View posts",
                "post.create": "Create posts",
                "post.update": "Update posts",
                "post.delete": "Delete posts",
                "post.publish": "Publish posts",
                "category.view": "View categories",
                "category.create": "Create categories",
                "category.update": "Update categories",
                "category.delete": "Delete categories",
                "settings.view": "View settings",
                "settings.update": "Update settings",
            }
            for code, desc in perm_map.items():
                Permission.objects.get_or_create(code=code, defaults={"description": desc})

            admin_role, _ = Role.objects.get_or_create(code="ROLE_ADMIN", defaults={"name": "Administrator"})
            auth_role, _ = Role.objects.get_or_create(
                code="ROLE_AUTHENTICATED", defaults={"name": "Authenticated User"}
            )

            for p in Permission.objects.all():
                RolePermission.objects.get_or_create(role=admin_role, permission=p)

            for code in ("post.view", "category.view"):
                p = Permission.objects.get(code=code)
                RolePermission.objects.get_or_create(role=auth_role, permission=p)

            with connection.cursor() as c:
                c.execute(
                    """
                    INSERT INTO user_roles (user_id, role_id)
                    SELECT u.id,
                           CASE WHEN u.role = 'ROLE_ADMIN' THEN %s ELSE %s END
                    FROM users u
                    ON CONFLICT DO NOTHING
                    """,
                    [admin_role.id, auth_role.id],
                )

            email = settings.APP_SEED_ADMIN_EMAIL.lower().strip()
            if not User.objects.filter(email=email).exists():
                User.objects.create(
                    full_name="System Admin",
                    email=email,
                    password=hash_password(settings.APP_SEED_ADMIN_PASSWORD),
                    role="ROLE_ADMIN",
                    created_at=now,
                    updated_at=now,
                )
                self.stdout.write(self.style.SUCCESS(f"Created admin user {email}"))
            else:
                self.stdout.write("Admin user already exists")

        self.stdout.write(self.style.SUCCESS("Done."))
