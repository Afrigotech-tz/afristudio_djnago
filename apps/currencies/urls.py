from django.urls import path
from .views import CurrencyListCreateView, CurrencyDetailView

urlpatterns = [
    path('', CurrencyListCreateView.as_view(), name='currency-list'),
    path('<uuid:uuid>/', CurrencyDetailView.as_view(), name='currency-detail'),
]
