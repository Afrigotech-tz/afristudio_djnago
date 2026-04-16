# AfriStudio API

AfriStudio is a **digital art auction platform** for African artists. Full-stack **Django REST API** converted from Laravel, with live WebSocket bidding, multi-currency support, artist wallets, and complete CRUD operations.

## ✨ Key Features

- **Artworks & Categories**: Browse, upload, categorize artworks
- **Live Auctions**: Real-time bidding via WebSockets (Channels)
- **Multi-Currency**: USD, TZS, EUR, ZAR with live exchange rates
- **Secure Wallets**: Bid deposits, automatic refunds/payouts
- **Shopping Cart**: Direct purchases for sold artworks
- **Authentication**: JWT tokens, email verification, password reset
- **Notifications**: Email + SMS (Africa's Talking/Twilio)
- **Activity Logs**: Complete audit trail
- **Admin Panel**: Full Django admin interface
- **OpenAPI Docs**: Swagger UI at `/api/schema/swagger-ui/`

## 🛠 Tech Stack

```
Django 5 + DRF + PostgreSQL 15
JWT Auth (SimpleJWT)
WebSockets (Django Channels)
API Docs (drf-spectacular)
Payments (Wallet system)
SMS (Africa's Talking)
Email (SMTP)
Redis (production WebSockets)
```

## 🚀 Quick Start (Development)

### Prerequisites
- Python 3.11+
- PostgreSQL 13+
- Redis (production only)

### 1. Setup

```bash
git clone <your-repo> afristudio
cd afristudio/django_project
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate     # Windows
pip install -r requirements.txt
```

### 2. Environment (.env)

```bash
cp .env.example .env
```

**Required vars:**
```
SECRET_KEY=django-insecure-change-in-production
DEBUG=True
DB_NAME=afristudio
DB_USER=postgres
DB_PASSWORD=password
DB_HOST=localhost
DB_PORT=5432

# Email
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your@gmail.com
EMAIL_HOST_PASSWORD=app-password

# SMS (Africa's Talking)
SMS_PROVIDER=africas_talking
SMS_AT_USERNAME=sandbox
SMS_AT_API_KEY=your-key
```

### 3. Database & Migrations

```bash
createdb afristudio  # PostgreSQL
python manage.py migrate
python manage.py createsuperuser
```

### 4. Seed Test Data

```bash
# All seed data (users, currencies, categories, roles)
python manage.py seed

# Specific seeds
python manage.py seed_currencies
python manage.py seed_users
python manage.py seed_countries
```

### 5. Run Server

```bash
python manage.py runserver
```

**URLs:**
- API Base: `http://localhost:8000/api/`
- Swagger Docs: `http://localhost:8000/api/schema/swagger-ui/`
- Admin: `http://localhost:8000/admin/`
- WebSockets: `ws://localhost:8000/ws/auctions/{uuid}/`

## 📱 API Usage Flow

### 1. Authentication
```bash
# Register
curl -X POST http://localhost:8000/api/auth/register \
  -d "email=user@example.com&password=password123&name=Test User"

# Login → JWT tokens
curl -X POST http://localhost:8000/api/auth/login \
  -d "email=user@example.com&password=password123"
```

### 2. Browse Public Data
```bash
curl "http://localhost:8000/api/categories/"
curl "http://localhost:8000/api/artworks/?currency=TZS"
curl "http://localhost:8000/api/auctions/"
curl "http://localhost:8000/api/currencies/public/"
```

### 3. Create Auction (Artist)
```bash
curl -X POST http://localhost:8000/api/auctions/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "artwork_uuid": "uuid-here",
    "start_price": "100.00",
    "bid_increment": "10.00",
    "currency": "USD",
    "start_time": "2024-01-01T10:00:00Z",
    "end_time": "2024-01-01T11:00:00Z"
  }'
```

### 4. Live Bidding (WebSocket)
```
ws://localhost:8000/ws/auctions/{auction-uuid}/
→ {"type": "auction_update", "data": {...}}
```

## 🧪 End-to-End Test

1. `POST /api/auth/register` → New user
2. `POST /api/auth/login` → JWT token  
3. `GET /api/categories/` → Browse categories
4. `POST /api/auctions/` → Create auction
5. `POST /api/auctions/{uuid}/start/` → Go live
6. `POST /api/auctions/{uuid}/bid/` → Place bids
7. **Watch WebSocket** for live updates!

## 🔧 Useful Commands

```bash
# API Schema
python manage.py spectacular --file schema.yaml

# Django Shell (+IPython)
pip install ipython
python manage.py shell

# Check migrations  
python manage.py showmigrations

# Test email
python manage.py sendtestemail your@email.com

# Reset DB (dangerous!)
python manage.py flush
python manage.py migrate
python manage.py seed
```

## ☁️ Production Deployment

### Docker (Recommended)
```bash
docker-compose up -d postgres redis
docker-compose up --build
```

### Gunicorn + Daphne
```bash
pip install gunicorn[standard]
gunicorn config.asgi:application -w 3 -b 0.0.0.0:8000
```

### Nginx Config
```
location /ws/ { proxy_pass http://127.0.0.1:8000; proxy_http_version 1.1; proxy_set_header Upgrade $http_upgrade; }
location /media/ { alias /path/to/media; }
```

## 🐛 Troubleshooting

| Issue | Solution |
|-------|----------|
| `401 Unauthorized` | Check JWT token expiry, use `Bearer` prefix |
| WebSocket fails | Ensure `daphne` first in `INSTALLED_APPS` |
| Currency conversion | Seed currencies: `python manage.py seed_currencies` |
| Email not sending | Check `.env` SMTP settings, test with `console` backend |
| Migrations fail | `python manage.py makemigrations --empty apps.artworks` |

## 🤝 Contributing

1. Fork repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push & PR to `develop`

**Linting**: `black .` | **Tests**: Coming soon!

## 📄 License

Proprietary software for AfriStudio.

---

**Empowering African artists through digital auctions** 🌍🎨
