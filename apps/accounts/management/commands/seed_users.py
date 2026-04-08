from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import Profile, User


ADMIN_USERS = [
    {
        'name':         'Super Administrator',
        'email':        'admin@afristudio.com',
        'phone':        '+255000000001',
        'role':         'Super Admin',
        'is_staff':     True,
        'is_superuser': True,
    },
    {
        'name':         'System Moderator',
        'email':        'moderator@afristudio.com',
        'phone':        '+255000000002',
        'role':         'Moderator',
        'is_staff':     True,
        'is_superuser': False,
    },
    {
        'name':         'Lead Artist',
        'email':        'artist@afristudio.com',
        'phone':        '+255000000003',
        'role':         'Artist',
        'is_staff':     False,
        'is_superuser': False,
    },
]

DEFAULT_PASSWORD = 'afristudio@2026'


class Command(BaseCommand):
    help = 'Seed administrative users'

    def handle(self, *args, **kwargs):
        for data in ADMIN_USERS:
            user, created = User.objects.update_or_create(
                email=data['email'],
                defaults={
                    'name':         data['name'],
                    'phone':        data['phone'],
                    'verified_at':  timezone.now(),
                    'is_active':    True,
                    'is_staff':     data['is_staff'],
                    'is_superuser': data['is_superuser'],
                },
            )
            # Always (re)set password so re-running the seeder is idempotent
            user.set_password(DEFAULT_PASSWORD)
            user.save(update_fields=['password'])

            # Assign role (Group)
            try:
                group = Group.objects.get(name=data['role'])
                user.groups.set([group])
            except Group.DoesNotExist:
                self.stdout.write(
                    self.style.WARNING(
                        f"Role '{data['role']}' not found — run seed_roles_permissions first."
                    )
                )

            # Create profile if missing
            Profile.objects.get_or_create(
                user=user,
                defaults={'bio': f"Official {data['role']} account for AfriStudio."},
            )

        self.stdout.write(
            self.style.SUCCESS(f'Admin users seeded successfully ({len(ADMIN_USERS)} records).')
        )
