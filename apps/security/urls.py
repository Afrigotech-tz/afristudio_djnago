from django.urls import path
from .views import (
    BlockedIPListCreateView, BlockedIPDetailView,
    BlockedDeviceListView, BlockedDeviceDetailView,
    RateLimitViolationListView, RateLimitViolationDetailView,
    SecurityConfigView, SecurityStatsView,
)

urlpatterns = [
    path('config/',                    SecurityConfigView.as_view()),
    path('stats/',                     SecurityStatsView.as_view()),
    # IP-level blocks
    path('blocked-ips/',               BlockedIPListCreateView.as_view()),
    path('blocked-ips/<int:pk>/',      BlockedIPDetailView.as_view()),
    # Device-level blocks
    path('blocked-devices/',           BlockedDeviceListView.as_view()),
    path('blocked-devices/<int:pk>/',  BlockedDeviceDetailView.as_view()),
    # Violations
    path('violations/',                RateLimitViolationListView.as_view()),
    path('violations/<int:pk>/',       RateLimitViolationDetailView.as_view()),
    path('violations/<int:pk>/block/', RateLimitViolationDetailView.as_view()),
]
