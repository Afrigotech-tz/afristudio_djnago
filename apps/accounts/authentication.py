"""
accounts/authentication.py

LenientJWTAuthentication — same as JWTAuthentication but silently returns
anonymous access when the token is missing, invalid, or expired.

Use this on public endpoints that should also recognise logged-in users when
a valid token IS present (e.g. GET /api/artworks/, GET /api/auctions/).
"""

from rest_framework_simplejwt.authentication import JWTAuthentication


class LenientJWTAuthentication(JWTAuthentication):
    """
    Silently downgrades authentication failures to anonymous access instead
    of raising AuthenticationFailed (which would return HTTP 401).

    This allows IsAuthenticatedOrReadOnly / AllowAny permission classes to
    work correctly even when the client sends an expired or malformed token.
    """

    def authenticate(self, request):
        try:
            return super().authenticate(request)
        except Exception:
            return None


# ── drf-spectacular extension ─────────────────────────────────────────────────
# Tell spectacular to treat LenientJWTAuthentication exactly like the standard
# JWTAuthentication so it appears as "jwtAuth: bearerFormat JWT" in the schema.

try:
    from drf_spectacular.extensions import OpenApiAuthenticationExtension

    class LenientJWTAuthenticationExtension(OpenApiAuthenticationExtension):
        target_class = 'apps.accounts.authentication.LenientJWTAuthentication'
        name = 'jwtAuth'

        def get_security_definition(self, auto_schema):
            return {
                'type': 'http',
                'scheme': 'bearer',
                'bearerFormat': 'JWT',
            }
except ImportError:
    pass
