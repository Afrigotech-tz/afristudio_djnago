from django.urls import path
from .views import NotificationLogListView, NotificationResendView

urlpatterns = [
    path('',            NotificationLogListView.as_view(), name='notification-log-list'),
    path('<int:pk>/resend/', NotificationResendView.as_view(), name='notification-resend'),
]
