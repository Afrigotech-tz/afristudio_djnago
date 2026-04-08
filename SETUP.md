# AfriStudio — Django REST Framework

Converted from Laravel 11 + Sanctum to **Django 4.2 + DRF + SimpleJWT**.

---

## Quick Start

### 1. Create & activate a virtual environment
```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure environment
```bash
cp .env.example .env
# Edit .env — set your DB credentials, SECRET_KEY, etc.
```

### 4. Run migrations
```bash
python manage.py migrate
```

### 5. Create a superuser (optional)
```bash
python manage.py createsuperuser
```

### 6. Start the dev server
```bash
python manage.py runserver
```

---

## API Endpoints

All endpoints are prefixed with `/api/`.

### Authentication  →  `/api/auth/`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/auth/register` | ❌ | Register (email or phone + password) |
| POST | `/api/auth/verify-account` | ❌ | Verify account with 6-digit OTP |
| POST | `/api/auth/login` | ❌ | Login → returns `access_token` + `refresh_token` |
| POST | `/api/auth/forgot-password` | ❌ | Request reset OTP |
| POST | `/api/auth/reset-password` | ❌ | Reset password with OTP |
| POST | `/api/auth/token/refresh` | ❌ | Refresh JWT access token |
| GET  | `/api/me` | ✅ | Get current user |
| POST | `/api/logout` | ✅ | Logout (blacklists refresh token) |

### Profile  →  `/api/profile/`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET    | `/api/profile/` | ✅ | Get authenticated user's profile |
| POST   | `/api/profile/` | ✅ | Create or update profile (supports avatar upload) |
| DELETE | `/api/profile/avatar` | ✅ | Remove avatar image |

### Artworks  →  `/api/artworks/`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET    | `/api/artworks/` | ❌ | List artworks (filter: `?category_uuid=`, `?is_sold=`, `?currency=TZS`) |
| POST   | `/api/artworks/` | ✅ | Create artwork (multipart/form-data with image) |
| GET    | `/api/artworks/<uuid>/` | ❌ | Get artwork details |
| PUT    | `/api/artworks/<uuid>/` | ✅ | Update artwork |
| DELETE | `/api/artworks/<uuid>/` | ✅ | Delete artwork |

### Categories  →  `/api/categories/`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET    | `/api/categories/` | ❌ | List categories (with artwork count) |
| POST   | `/api/categories/` | ✅ | Create category |
| GET    | `/api/categories/<uuid>/` | ❌ | Get category |
| PUT    | `/api/categories/<uuid>/` | ✅ | Update category |
| DELETE | `/api/categories/<uuid>/` | ✅ | Delete category |

### Currencies  →  `/api/currencies/`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET    | `/api/currencies/` | ✅ | List currencies |
| POST   | `/api/currencies/` | ✅ | Create currency |
| GET    | `/api/currencies/<uuid>/` | ✅ | Get currency |
| PUT    | `/api/currencies/<uuid>/` | ✅ | Update currency |
| DELETE | `/api/currencies/<uuid>/` | ✅ | Delete currency |

### Activity Logs  →  `/api/activity-logs/`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/activity-logs/` | ✅ | List logs (filter: `?search=`, `?log_name=`, `?event=`, `?causer_email=`) |

---

## Authentication

This project uses **JWT (SimpleJWT)** instead of Laravel Sanctum.

```bash
# Login
POST /api/auth/login
{ "login": "john@example.com", "password": "password123" }

# Response
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "Bearer",
  "user": { ... }
}

# Use the access token in headers
Authorization: Bearer <access_token>

# Refresh when expired
POST /api/auth/token/refresh
{ "refresh": "<refresh_token>" }
```

---

## Key Laravel → Django Mapping

| Laravel | Django |
|---------|--------|
| Eloquent Models | Django ORM Models |
| Form Requests | DRF Serializers (validation) |
| API Resources | DRF Serializers (output) |
| Route Model Binding (uuid) | `lookup_field = 'uuid'` on ViewSets |
| Sanctum tokens | SimpleJWT access + refresh tokens |
| Spatie Roles/Permissions | Django Groups + PermissionsMixin |
| Spatie Activity Log | Custom `ActivityLog` model + `log_activity()` util |
| `storage/app/public` | `MEDIA_ROOT` / `MEDIA_URL` |
| `php artisan migrate` | `python manage.py migrate` |

---

## Project Structure

```
django_project/
├── manage.py
├── requirements.txt
├── .env.example
├── config/
│   ├── settings.py       # Main settings (DB, JWT, CORS, DRF)
│   ├── urls.py           # Root URL configuration
│   └── wsgi.py
└── apps/
    ├── accounts/         # User, Profile, Country + Auth endpoints
    ├── artworks/         # Artwork, Category + endpoints
    ├── currencies/       # Currency + endpoints
    └── activity_logs/    # ActivityLog model + list endpoint
```
