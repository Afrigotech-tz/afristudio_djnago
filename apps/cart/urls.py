from django.urls import path
from .views import CartView, CartItemAddView, CartItemRemoveView

urlpatterns = [
    path('', CartView.as_view(), name='cart'),
    path('items/', CartItemAddView.as_view(), name='cart-item-add'),
    path('items/<uuid:uuid>/', CartItemRemoveView.as_view(), name='cart-item-remove'),
]
