"""
accounts/urls/admin_urls.py
All routes under /api/admin/  — require is_staff or is_superuser.
"""

from django.urls import path
from apps.accounts.admin_views import (
    # Roles
    RoleListCreateView,
    RoleDetailView,
    PermissionListView,
    # Users
    AdminUserListView,
    AdminUserDetailView,
    AdminAssignRoleView,
    AdminRemoveRoleView,
    # Content
    AdminArtworkListView,
    AdminArtworkDetailView,
    AdminOrderListView,
    AdminOrderDetailView,
    AdminOrderStatusView,
    AdminCartListView,
)

admin_urlpatterns = [
    # Roles & permissions
    path('roles/',                              RoleListCreateView.as_view(),   name='admin-roles'),
    path('roles/<int:pk>/',                     RoleDetailView.as_view(),       name='admin-role-detail'),
    path('permissions/',                        PermissionListView.as_view(),   name='admin-permissions'),

    # Users
    path('users/',                              AdminUserListView.as_view(),    name='admin-users'),
    path('users/<uuid:uuid>/',                  AdminUserDetailView.as_view(),  name='admin-user-detail'),
    path('users/<uuid:uuid>/assign-role/',      AdminAssignRoleView.as_view(),  name='admin-user-assign-role'),
    path('users/<uuid:uuid>/remove-role/',      AdminRemoveRoleView.as_view(),  name='admin-user-remove-role'),

    # Content
    path('artworks/',                           AdminArtworkListView.as_view(), name='admin-artworks'),
    path('artworks/<uuid:uuid>/',               AdminArtworkDetailView.as_view(), name='admin-artwork-detail'),
    path('orders/',                             AdminOrderListView.as_view(),   name='admin-orders'),
    path('orders/<uuid:uuid>/',                 AdminOrderDetailView.as_view(), name='admin-order-detail'),
    path('orders/<uuid:uuid>/status/',          AdminOrderStatusView.as_view(), name='admin-order-status'),
    path('carts/',                              AdminCartListView.as_view(),    name='admin-carts'),
]
