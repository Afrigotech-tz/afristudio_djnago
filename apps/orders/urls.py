from django.urls import path
from .views import CheckoutView, OrderListView, OrderDetailView, OrderStatusUpdateView

urlpatterns = [
    path('', OrderListView.as_view(), name='order-list'),
    path('checkout/', CheckoutView.as_view(), name='order-checkout'),
    path('<uuid:uuid>/', OrderDetailView.as_view(), name='order-detail'),
    path('<uuid:uuid>/status/', OrderStatusUpdateView.as_view(), name='order-status-update'),
]
