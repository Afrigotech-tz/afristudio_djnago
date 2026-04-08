"""
Equivalent to Laravel's RolesAndPermissionsSeeder.
Roles  → Django auth.Group
Permissions → Django auth.Permission (linked to the User content type)
"""

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

from apps.accounts.models import User


CUSTOM_PERMISSIONS = [
    'upload pictures',
    'edit pictures',
    'delete pictures',
    'approve pictures',
    'place bids',
    'view bids',
    'cancel bids',
    'manage users',
    'view analytics',
]

ROLES = {
    'Super Admin': CUSTOM_PERMISSIONS,
    'Moderator':   ['approve pictures', 'delete pictures', 'view bids', 'manage users'],
    'Artist':      ['upload pictures', 'edit pictures', 'delete pictures', 'view bids'],
    'Bidder':      ['place bids', 'view bids'],
}


def _codename(name: str) -> str:
    """Convert permission name to a Django-safe codename."""
    return name.replace(' ', '_')


class Command(BaseCommand):
    help = 'Seed roles (Groups) and custom permissions'

    def handle(self, *args, **kwargs):
        # All custom permissions are attached to the User content type
        ct = ContentType.objects.get_for_model(User)

        # Create / retrieve all custom permissions
        perm_map: dict[str, Permission] = {}
        for perm_name in CUSTOM_PERMISSIONS:
            perm, _ = Permission.objects.get_or_create(
                codename=_codename(perm_name),
                content_type=ct,
                defaults={'name': perm_name},
            )
            perm_map[perm_name] = perm

        # Create roles (Groups) and assign permissions
        for role_name, role_perms in ROLES.items():
            group, _ = Group.objects.get_or_create(name=role_name)
            group.permissions.set([perm_map[p] for p in role_perms])

        self.stdout.write(
            self.style.SUCCESS(
                f'Roles & permissions seeded successfully '
                f'({len(ROLES)} roles, {len(CUSTOM_PERMISSIONS)} permissions).'
            )
        )
