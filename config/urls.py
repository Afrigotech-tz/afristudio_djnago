from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)

from apps.accounts.urls.auth_urls import auth_urlpatterns, user_urlpatterns

urlpatterns = [
    path('admin/', admin.site.urls),

    # OpenAPI schema + UI
    path('api/schema/',  SpectacularAPIView.as_view(),    name='schema'),
    path('api/docs/',    SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/',   SpectacularRedocView.as_view(url_name='schema'),   name='redoc'),

    # Auth routes  — mirrors Laravel's Route::prefix('auth') group
    path('api/auth/', include(auth_urlpatterns)),

    # Authenticated user routes  — /api/me  /api/logout
    path('api/', include(user_urlpatterns)),

    # Profile  — /api/profile/
    path('api/profile/', include('apps.accounts.urls.profile_urls')),

    # Artworks & Categories  (public list/show, auth required for CUD)
    path('api/artworks/', include('apps.artworks.urls.artwork_urls')),
    path('api/categories/', include('apps.artworks.urls.category_urls')),

    # Currencies  (all routes require auth per original Laravel routes)
    path('api/currencies/', include('apps.currencies.urls')),

    # Activity logs  (auth required, read-only)
    path('api/activity-logs/', include('apps.activity_logs.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
