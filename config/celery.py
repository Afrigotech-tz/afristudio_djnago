"""
config/celery.py
Celery application entry-point for AfriStudio.

Broker: Redis (redis://localhost:6379/0 by default — override via CELERY_BROKER_URL env var)
Result backend: Redis (same instance)

Start a worker in development:
    celery -A config worker --loglevel=info
"""

import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('afristudio')

# Read config from Django settings, namespace 'CELERY_'
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks.py in every INSTALLED_APP
app.autodiscover_tasks()
