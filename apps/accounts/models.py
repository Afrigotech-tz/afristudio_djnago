"""
accounts/models.py
Equivalent to Laravel's User, Profile, Country, Role models.
- Uses Django's built-in AbstractBaseUser + PermissionsMixin
- Roles via Django Groups (replaces Spatie Permission)
- UUID field on every model (NOT the PK, just a public identifier)
"""

import uuid
from django.db import models
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
    Group,
)
from django.utils import timezone


# ──────────────────────────────────────────────
# Country
# ──────────────────────────────────────────────
class Country(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    name = models.CharField(max_length=100, unique=True)
    iso_code = models.CharField(max_length=2, unique=True)
    phone_code = models.CharField(max_length=5, blank=True, null=True)
    currency_code = models.CharField(max_length=3, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'countries'
        verbose_name_plural = 'countries'
        ordering = ['name']

    def __str__(self):
        return self.name


# ──────────────────────────────────────────────
# Custom User Manager
# ──────────────────────────────────────────────
class UserManager(BaseUserManager):
    def create_user(self, name, password=None, email=None, phone=None, **extra_fields):
        if not email and not phone:
            raise ValueError('Either email or phone must be provided.')
        if email:
            email = self.normalize_email(email)
        user = self.model(name=name, email=email, phone=phone, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, name, password, email=None, phone=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('verified_at', timezone.now())
        return self.create_user(name, password, email, phone, **extra_fields)


# ──────────────────────────────────────────────
# User  (replaces Laravel's User model + HasRoles)
# ──────────────────────────────────────────────
class User(AbstractBaseUser, PermissionsMixin):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True, null=True, blank=True)
    phone = models.CharField(max_length=20, unique=True, null=True, blank=True)
    phone_verified_at = models.DateTimeField(null=True, blank=True)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    verification_code = models.CharField(max_length=6, null=True, blank=True)
    country = models.ForeignKey(
        Country, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='users'
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    bidding_banned_until = models.DateTimeField(null=True, blank=True, help_text='Bidding suspended until this datetime. Null = no ban.')
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['name']

    objects = UserManager()

    class Meta:
        db_table = 'users'

    def __str__(self):
        return self.email or self.phone or self.name

    def is_verified(self) -> bool:
        return self.verified_at is not None

    # ── Helpers that mirror Laravel's HasRoles (using Django Groups) ──
    def get_role_names(self):
        return list(self.groups.values_list('name', flat=True))

    def assign_role(self, role_name: str):
        group, _ = Group.objects.get_or_create(name=role_name)
        self.groups.add(group)

    _APP_LABELS = {
        'accounts', 'artworks', 'auctions', 'orders', 'cart',
        'wallet', 'currencies', 'site_config', 'security',
        'notifications', 'activity_logs', 'payments',
    }

    def get_all_permissions_list(self):
        """
        Return effective permissions: role-based (group) permissions PLUS any
        directly-assigned user_permissions within the allowed app labels.

        Only users who are BOTH is_superuser=True AND is_staff=True are treated
        as full admins and receive all app permissions.
        """
        from django.contrib.auth.models import Permission

        if self.is_superuser and self.is_staff:
            return sorted(
                f'{p.content_type.app_label}.{p.codename}'
                for p in Permission.objects.select_related('content_type').filter(
                    content_type__app_label__in=self._APP_LABELS
                )
            )

        perms: set[str] = set()
        # Role-based permissions
        for group in self.groups.prefetch_related('permissions__content_type').all():
            for perm in group.permissions.all():
                label = perm.content_type.app_label
                if label in self._APP_LABELS:
                    perms.add(f'{label}.{perm.codename}')
        # Directly-assigned permissions
        for perm in self.user_permissions.select_related('content_type').all():
            label = perm.content_type.app_label
            if label in self._APP_LABELS:
                perms.add(f'{label}.{perm.codename}')
        return sorted(perms)


# ──────────────────────────────────────────────
# Profile  (one-to-one extension of User)
# ──────────────────────────────────────────────
class Profile(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    bio = models.TextField(null=True, blank=True)
    address = models.CharField(max_length=255, null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'profiles'

    def __str__(self):
        return f"Profile of {self.user}"


# ──────────────────────────────────────────────
# Address  (multiple per user, one is default)
# ──────────────────────────────────────────────
class Address(models.Model):
    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='addresses')
    label      = models.CharField(max_length=50, blank=True, default='', help_text='e.g. Home, Work, Other')
    full_name  = models.CharField(max_length=255)
    phone      = models.CharField(max_length=30, blank=True, default='')
    address    = models.TextField()
    city       = models.CharField(max_length=100)
    country    = models.CharField(max_length=100, default='Tanzania')
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'addresses'
        ordering = ['-is_default', '-created_at']

    def set_as_default(self):
        Address.objects.filter(user=self.user, is_default=True).exclude(pk=self.pk).update(is_default=False)
        self.is_default = True
        self.save(update_fields=['is_default'])

    def __str__(self):
        return f"{self.label or 'Address'} — {self.user}"
