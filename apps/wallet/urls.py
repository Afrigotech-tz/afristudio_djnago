from django.urls import path
from .views import WalletView, WalletDepositView, AdminWalletListView, AdminWalletCreditView

urlpatterns = [
    path('', WalletView.as_view(), name='wallet'),
    path('deposit/', WalletDepositView.as_view(), name='wallet-deposit'),
]

admin_urlpatterns = [
    path('wallets/', AdminWalletListView.as_view(), name='admin-wallets'),
    path('wallets/<int:pk>/credit/', AdminWalletCreditView.as_view(), name='admin-wallet-credit'),
]
