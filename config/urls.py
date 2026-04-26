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
from apps.accounts.urls.admin_urls import admin_urlpatterns
from apps.wallet.urls import admin_urlpatterns as wallet_admin_urlpatterns

urlpatterns = [
    path('admin/', admin.site.urls),

    # OpenAPI schema + UI
    path('api/schema/',  SpectacularAPIView.as_view(),    name='schema'),
    path('api/docs/',    SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/',   SpectacularRedocView.as_view(url_name='schema'),   name='redoc'),

    # Auth routes
    path('api/auth/', include(auth_urlpatterns)),

    # Authenticated user routes  — /api/me  /api/logout
    path('api/', include(user_urlpatterns)),

    # Profile  — /api/profile/
    path('api/profile/', include('apps.accounts.urls.profile_urls')),

    # Addresses — /api/addresses/
    path('api/addresses/', include('apps.accounts.urls.address_urls')),

    # Artworks & Categories  (public list/show, auth required for CUD)
    path('api/artworks/', include('apps.artworks.urls.artwork_urls')),
    path('api/categories/', include('apps.artworks.urls.category_urls')),

    # Currencies  
    path('api/currencies/', include('apps.currencies.urls')),

    # Activity logs  (auth required, read-only)
    path('api/activity-logs/', include('apps.activity_logs.urls')),

    # Wallet
    path('api/wallet/', include('apps.wallet.urls')),

    # Auctions & live bidding
    path('api/auctions/', include('apps.auctions.urls')),

    # Cart
    path('api/cart/', include('apps.cart.urls')),

    # Orders & delivery
    path('api/orders/', include('apps.orders.urls')),

    # Payments
    path('api/payments/', include('apps.payments.urls')),

    # Admin management (roles, permissions, all content)
    path('api/admin/', include((admin_urlpatterns + wallet_admin_urlpatterns, 'admin_api'))),

    # Site configuration (hero image, contact info, contact messages)
    path('api/site/', include('apps.site_config.urls')),

    # Reports (admin-only)
    path('api/reports/', include('apps.reports.urls')),

    # Security — blocked IPs, rate-limit violations, performance stats
    path('api/security/', include('apps.security.urls')),

    # Notification logs
    path('api/notifications/', include('apps.notifications.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
