from django.urls import path
from .views import WalletView, WalletDepositView

urlpatterns = [
    path('', WalletView.as_view(), name='wallet'),
    path('deposit/', WalletDepositView.as_view(), name='wallet-deposit'),
]
