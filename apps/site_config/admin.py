from django.contrib import admin
from django.utils.html import format_html
from .models import LandingHero, ContactInfo, ContactMessage


@admin.register(LandingHero)
class LandingHeroAdmin(admin.ModelAdmin):
    readonly_fields = ['image_preview', 'updated_at']
    fields = ['image', 'image_preview', 'updated_at']

    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="max-height:200px;" />', obj.image.url)
        return '—'
    image_preview.short_description = 'Preview'

    def has_add_permission(self, request):
        return not LandingHero.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ContactInfo)
class ContactInfoAdmin(admin.ModelAdmin):
    readonly_fields = ['updated_at']
    fields = ['email', 'phone', 'location', 'updated_at']

    def has_add_permission(self, request):
        return not ContactInfo.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ['name', 'email', 'subject', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['name', 'email', 'subject', 'message']
    readonly_fields = ['name', 'email', 'subject', 'message', 'created_at', 'updated_at']
    fields = ['name', 'email', 'subject', 'message', 'status', 'created_at', 'updated_at']
    ordering = ['-created_at']

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return True
