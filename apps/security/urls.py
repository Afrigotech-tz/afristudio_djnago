from django.urls import path
from .views import (
    BlockedIPListCreateView,
    BlockedIPDetailView,
    RateLimitViolationListView,
    SecurityStatsView,
)

urlpatterns = [
    path('blocked-ips/',              BlockedIPListCreateView.as_view()),
    path('blocked-ips/<int:pk>/',     BlockedIPDetailView.as_view()),
    path('violations/',               RateLimitViolationListView.as_view()),
    path('violations/<int:pk>/',      RateLimitViolationListView.as_view()),
    path('stats/',                    SecurityStatsView.as_view()),
]
