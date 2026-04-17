"""
Django settings for AfriStudio API
Converted from Laravel to Django REST Framework
"""

from pathlib import Path
from datetime import timedelta
from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config('SECRET_KEY', default='django-insecure-change-me-in-production')
DEBUG = config('DEBUG', default=True, cast=bool)

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='*').split(',')

# ──────────────────────────────────────────────
# Application definition
# ──────────────────────────────────────────────
DJANGO_APPS = [
    'daphne',                                   # must be before django.contrib.staticfiles
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

THIRD_PARTY_APPS = [
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'django_filters',
    'drf_spectacular',
    'channels',
]

LOCAL_APPS = [
    'apps.accounts',
    'apps.artworks',
    'apps.currencies',
    'apps.activity_logs',
    'apps.notifications',
    'apps.wallet',
    'apps.auctions',
    'apps.cart',
    'apps.orders',
    'apps.site_config',
    'apps.reports',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

# ──────────────────────────────────────────────
# Django Channels — WebSocket layer
# Use InMemoryChannelLayer for development.
# For production switch to Redis:
#   pip install channels-redis
#   CHANNEL_LAYERS = {'default': {'BACKEND': 'channels_redis.core.RedisChannelLayer',
#                                 'CONFIG': {'hosts': [('127.0.0.1', 6379)]}}}
# ──────────────────────────────────────────────
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
    },
}

# ──────────────────────────────────────────────
# Database — PostgreSQL
# ──────────────────────────────────────────────
DATABASES = {
    'default': {
        'ENGINE': config('DB_ENGINE', default='django.db.backends.postgresql'),
        'NAME': config('DB_NAME', default='afristudio'),
        'USER': config('DB_USER', default='postgres'),
        'PASSWORD': config('DB_PASSWORD', default='password'),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
    }
}

# ──────────────────────────────────────────────
# Custom User Model
# ──────────────────────────────────────────────
AUTH_USER_MODEL = 'accounts.User'

# ──────────────────────────────────────────────
# Password validation
# ──────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ──────────────────────────────────────────────
# DRF Settings
# ──────────────────────────────────────────────
REST_FRAMEWORK = {
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_AUTHENTICATION_CLASSES': (
        # LenientJWT: silently ignores expired/invalid tokens so public
        # endpoints (IsAuthenticatedOrReadOnly / AllowAny) keep working
        # even when the client sends a stale token.
        'apps.accounts.authentication.LenientJWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ),
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
    ),
}

# ──────────────────────────────────────────────
# SimpleJWT Settings  
# ──────────────────────────────────────────────
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(
        minutes=config('ACCESS_TOKEN_LIFETIME_MINUTES', default=60, cast=int)
    ),
    'REFRESH_TOKEN_LIFETIME': timedelta(
        days=config('REFRESH_TOKEN_LIFETIME_DAYS', default=7, cast=int)
    ),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
}

# ──────────────────────────────────────────────
# CORS  (replaces Laravel's cors config)
# ──────────────────────────────────────────────
CORS_ALLOWED_ORIGINS = config(
    'CORS_ALLOWED_ORIGINS',
    default='http://localhost:3000'
).split(',')
CORS_ALLOW_CREDENTIALS = True

# ──────────────────────────────────────────────
# Media / Static Files
# ──────────────────────────────────────────────
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ──────────────────────────────────────────────
# Internationalization
# ──────────────────────────────────────────────
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Dar_es_Salaam'
USE_I18N = True
USE_TZ = True

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ──────────────────────────────────────────────
# Celery
# ──────────────────────────────────────────────
CELERY_BROKER_URL = config('CELERY_BROKER_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = config('CELERY_RESULT_BACKEND', default='redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 300  # 5 minutes hard limit per task

# ──────────────────────────────────────────────
# drf-spectacular  (OpenAPI 3 / Swagger / ReDoc)
# ──────────────────────────────────────────────
SPECTACULAR_SETTINGS = {
    'TITLE': 'AfriStudio API',
    'DESCRIPTION': (
        'REST API for AfriStudio - an African digital art auction platform.\n\n'
        '**Authentication:** Use the `/api/auth/login` endpoint to obtain a Bearer token, '
        'then click **Authorize** and enter `Bearer <your_token>`.'
    ),
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'CONTACT': {'name': 'AfriStudio Team', 'email': 'admin@afristudio.com'},
    'LICENSE': {'name': 'Proprietary'},
    'TAGS': [
        {'name': 'Auth',          'description': 'Register, verify, login, logout and token refresh'},
        {'name': 'Profile',       'description': 'View and update the authenticated user\'s profile'},
        {'name': 'Artworks',      'description': 'CRUD for artwork listings'},
        {'name': 'Categories',    'description': 'Artwork category management'},
        {'name': 'Currencies',    'description': 'Exchange-rate management'},
        {'name': 'Activity Logs', 'description': 'Read-only audit trail of system events'},
    ],
    'COMPONENT_SPLIT_REQUEST': True,
    'SCHEMA_PATH_PREFIX': '/api/',
    'SWAGGER_UI_SETTINGS': {
        'defaultModelsExpandDepth': -1,
    },
    'ENUM_NAME_OVERRIDES': {
        'AuctionStatusEnum':  'apps.auctions.models.Auction.STATUS_CHOICES',
        'OrderStatusEnum':    'apps.orders.models.Order.STATUS_CHOICES',
        'NotificationChannelEnum': 'apps.notifications.models.NotificationLog.CHANNEL_CHOICES',
        'NotificationStatusEnum':  'apps.notifications.models.NotificationLog.STATUS_CHOICES',
        'WalletTxTypeEnum':   'apps.wallet.models.WalletTransaction.TYPE_CHOICES',
        'CartItemSourceEnum': 'apps.cart.models.CartItem.SOURCE_CHOICES',
    },
}

# ──────────────────────────────────────────────
# Email
# ──────────────────────────────────────────────
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='noreply@afristudio.com')

# ──────────────────────────────────────────────
# SMS
# ──────────────────────────────────────────────
# Options: 'africas_talking' | 'twilio' | 'console'
SMS_PROVIDER = config('SMS_PROVIDER', default='console')

# Africa's Talking (recommended for Tanzania/Africa)
SMS_AT_USERNAME = config('SMS_AT_USERNAME', default='sandbox')
SMS_AT_API_KEY = config('SMS_AT_API_KEY', default='')
SMS_SENDER_ID = config('SMS_SENDER_ID', default='')  # Optional short-code / sender name

# Twilio (alternative)
SMS_TWILIO_ACCOUNT_SID = config('SMS_TWILIO_ACCOUNT_SID', default='')
SMS_TWILIO_AUTH_TOKEN = config('SMS_TWILIO_AUTH_TOKEN', default='')
SMS_TWILIO_FROM = config('SMS_TWILIO_FROM', default='')
