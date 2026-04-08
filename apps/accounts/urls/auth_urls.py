from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from apps.accounts.views import (
    RegisterView,
    VerifyAccountView,
    LoginView,
    LogoutView,
    MeView,
    ForgotPasswordView,
    ResetPasswordView,
)

# ──────────────────────────────────────────────
# Public auth endpoints  →  /api/auth/*
# ──────────────────────────────────────────────
auth_urlpatterns = [
    path('register', RegisterView.as_view(), name='auth-register'),
    path('verify-account', VerifyAccountView.as_view(), name='auth-verify'),
    path('login', LoginView.as_view(), name='auth-login'),
    path('forgot-password', ForgotPasswordView.as_view(), name='auth-forgot-password'),
    path('reset-password', ResetPasswordView.as_view(), name='auth-reset-password'),
    path('token/refresh', TokenRefreshView.as_view(), name='token-refresh'),
]

# ──────────────────────────────────────────────
# Authenticated endpoints  →  /api/*
# ──────────────────────────────────────────────
user_urlpatterns = [
    path('me', MeView.as_view(), name='auth-me'),
    path('logout', LogoutView.as_view(), name='auth-logout'),
]

# Default export (used when included directly)
urlpatterns = auth_urlpatterns
