from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Profile, Country


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['uuid', 'name', 'email', 'phone', 'is_verified', 'is_staff']
    search_fields = ['name', 'email', 'phone']
    ordering = ['-created_at']
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal', {'fields': ('name', 'phone', 'country')}),
        ('Verification', {'fields': ('verification_code', 'verified_at', 'email_verified_at', 'phone_verified_at')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('name', 'email', 'phone', 'password1', 'password2'),
        }),
    )

    def is_verified(self, obj):
        return obj.is_verified()
    is_verified.boolean = True


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ['uuid', 'user', 'city']
    search_fields = ['user__email', 'user__name', 'city']


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ['name', 'iso_code', 'phone_code', 'currency_code']
    search_fields = ['name', 'iso_code']
