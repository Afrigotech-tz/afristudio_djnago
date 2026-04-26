from django.urls import path
from .views import (
    ActivePaymentMethodsView, AdminPaymentMethodsView, AdminPaymentMethodDetailView,
    InitiatePaymentView, BankTransferSubmitView,
    StripeWebhookView, SelcomCallbackView,
    TransactionListView, TransactionDetailView,
    ConfirmTransactionView, CancelTransactionView,
)

urlpatterns = [
    # Payment methods
    path('methods/',               ActivePaymentMethodsView.as_view(),        name='payment-methods'),
    path('methods/admin/',         AdminPaymentMethodsView.as_view(),         name='payment-methods-admin'),
    path('methods/<str:channel>/', AdminPaymentMethodDetailView.as_view(),    name='payment-method-detail'),

    # Initiate & submit
    path('initiate/',                   InitiatePaymentView.as_view(),        name='payment-initiate'),
    path('bank-transfer/submit/',       BankTransferSubmitView.as_view(),     name='bank-transfer-submit'),

    # Gateway webhooks / callbacks (no auth)
    path('stripe/webhook/',             StripeWebhookView.as_view(),          name='stripe-webhook'),
    path('selcom/callback/',            SelcomCallbackView.as_view(),         name='selcom-callback'),

    # Transactions
    path('transactions/',               TransactionListView.as_view(),        name='transaction-list'),
    path('transactions/<int:pk>/',      TransactionDetailView.as_view(),      name='transaction-detail'),
    path('transactions/<int:pk>/confirm/', ConfirmTransactionView.as_view(),  name='transaction-confirm'),
    path('transactions/<int:pk>/cancel/',  CancelTransactionView.as_view(),   name='transaction-cancel'),
]
