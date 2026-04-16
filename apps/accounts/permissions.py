"""
accounts/permissions.py
Reusable DRF permission classes used across the project.
"""

from rest_framework.permissions import BasePermission


class IsAdminOrStaff(BasePermission):
    """
    Allows access only to users who are Django staff (is_staff=True)
    or superusers (is_superuser=True).
    """
    message = 'You do not have permission to perform this action.'

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and (request.user.is_staff or request.user.is_superuser)
        )


class IsAdminOrStaffOrReadOnly(BasePermission):
    """
    Read-only for everyone; write access only for staff/admin.
    """
    def has_permission(self, request, view):
        from rest_framework.permissions import SAFE_METHODS
        if request.method in SAFE_METHODS:
            return True
        return bool(
            request.user
            and request.user.is_authenticated
            and (request.user.is_staff or request.user.is_superuser)
        )
