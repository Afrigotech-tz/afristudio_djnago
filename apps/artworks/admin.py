from django.contrib import admin
from .models import Category, Artwork


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['uuid', 'name', 'slug']
    search_fields = ['name']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Artwork)
class ArtworkAdmin(admin.ModelAdmin):
    list_display = ['uuid', 'name', 'category', 'base_price', 'is_sold', 'created_at']
    list_filter = ['is_sold', 'category']
    search_fields = ['name']
