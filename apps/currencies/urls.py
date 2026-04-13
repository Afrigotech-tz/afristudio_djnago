from django.urls import path
from .views import CurrencyListCreateView, CurrencyDetailView, PublicCurrencyListView

urlpatterns = [
    path('', CurrencyListCreateView.as_view(), name='currency-list'),
    path('public/', PublicCurrencyListView.as_view(), name='currency-list-public'),
    path('<uuid:uuid>/', CurrencyDetailView.as_view(), name='currency-detail'),
]
