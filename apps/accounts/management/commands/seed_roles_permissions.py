"""
Equivalent to Laravel's RolesAndPermissionsSeeder.
Roles  → Django auth.Group
Custom permissions → Django auth.Permission (linked to the User content type)

Role design:
  Super Admin  — full access (all app permissions)
  Moderator    — content moderation + user oversight
  Artist       — manage own artworks + bidding
  Bidder       — bidding + orders only
"""

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

from apps.accounts.models import User

# ── Custom (non-model) permissions ────────────────────────────────────────────
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

# ── App namespaces that are part of our system ────────────────────────────────
APP_LABELS = {
    'accounts', 'artworks', 'auctions', 'orders', 'cart',
    'wallet', 'currencies', 'site_config', 'security',
    'notifications', 'activity_logs', 'payments',
}

# ── Permission codenames granted to each role ─────────────────────────────────
# Format: 'app.codename'  — resolved against Django's Permission table.
# Custom permissions use 'accounts.<codename>' since they are on the User ct.
ROLE_PERMISSIONS = {
    'Super Admin': '__all__',   # special sentinel — gets every app permission

    'Moderator': [
        # artworks
        'artworks.view_artwork', 'artworks.change_artwork', 'artworks.delete_artwork',
        'artworks.view_category',
        # auctions
        'auctions.view_auction', 'auctions.view_bid', 'auctions.view_auctionwinner',
        'auctions.view_auctionpaymentviolation',
        # orders
        'orders.view_order', 'orders.view_orderitem',
        # users / accounts
        'accounts.view_user', 'accounts.manage_users', 'accounts.approve_pictures',
        'accounts.view_bids', 'accounts.cancel_bids',
        # activity & notifications
        'activity_logs.view_activitylog',
        'notifications.view_notificationlog',
        # site content
        'site_config.view_contactmessage', 'site_config.change_contactmessage',
    ],

    'Artist': [
        # own artworks
        'artworks.view_artwork', 'artworks.add_artwork',
        'artworks.change_artwork', 'artworks.delete_artwork',
        'artworks.view_category',
        # auctions — participate
        'auctions.view_auction', 'auctions.add_bid', 'auctions.view_bid',
        # orders & cart
        'orders.view_order', 'orders.add_order',
        'cart.view_cart', 'cart.add_cartitem', 'cart.change_cartitem', 'cart.delete_cartitem',
        # wallet
        'wallet.view_wallet', 'wallet.view_wallettransaction',
        # payments (initiate own payment)
        'payments.add_paymenttransaction', 'payments.view_paymenttransaction',
        'payments.view_paymentmethod',
        # custom
        'accounts.upload_pictures', 'accounts.edit_pictures',
        'accounts.delete_pictures', 'accounts.view_bids',
        # currencies (read-only — needed for display)
        'currencies.view_currency',
    ],

    'Bidder': [
        # auctions
        'auctions.view_auction', 'auctions.add_bid', 'auctions.view_bid',
        # orders & cart
        'orders.view_order', 'orders.add_order',
        'cart.view_cart', 'cart.add_cartitem', 'cart.change_cartitem', 'cart.delete_cartitem',
        # wallet
        'wallet.view_wallet', 'wallet.view_wallettransaction',
        # payments
        'payments.add_paymenttransaction', 'payments.view_paymenttransaction',
        'payments.view_paymentmethod',
        # custom
        'accounts.place_bids', 'accounts.view_bids',
        # currencies
        'currencies.view_currency',
    ],
}


def _codename(name: str) -> str:
    return name.replace(' ', '_')


class Command(BaseCommand):
    help = 'Seed roles (Groups) and reset their permissions to correct defaults'

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true',
                            help='Force-reset existing role permissions to defaults')

    def handle(self, *args, **options):
        ct = ContentType.objects.get_for_model(User)

        # ── Ensure custom permissions exist ───────────────────────────────────
        for perm_name in CUSTOM_PERMISSIONS:
            Permission.objects.get_or_create(
                codename=_codename(perm_name),
                content_type=ct,
                defaults={'name': perm_name},
            )

        # ── All app permissions (for Super Admin) ─────────────────────────────
        all_app_perms = list(
            Permission.objects
            .filter(content_type__app_label__in=APP_LABELS)
        )

        # ── Build a codename→Permission lookup ────────────────────────────────
        perm_lookup: dict[str, Permission] = {
            f'{p.content_type.app_label}.{p.codename}': p
            for p in Permission.objects.select_related('content_type')
            .filter(content_type__app_label__in=APP_LABELS)
        }

        created_roles = []
        for role_name, role_perms in ROLE_PERMISSIONS.items():
            group, created = Group.objects.get_or_create(name=role_name)

            if created or options.get('reset'):
                if role_perms == '__all__':
                    group.permissions.set(all_app_perms)
                else:
                    resolved = []
                    for key in role_perms:
                        p = perm_lookup.get(key)
                        if p:
                            resolved.append(p)
                        else:
                            self.stdout.write(self.style.WARNING(f'  Permission not found: {key}'))
                    group.permissions.set(resolved)
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'  {"Created" if created else "Reset"} "{role_name}" '
                            f'— {len(resolved)} permissions'
                        )
                    )
            else:
                self.stdout.write(f'  Skipped "{role_name}" (already exists, use --reset to overwrite)')

            created_roles.append(role_name)

        self.stdout.write(self.style.SUCCESS(
            f'\nDone. Roles: {", ".join(created_roles)}'
        ))
