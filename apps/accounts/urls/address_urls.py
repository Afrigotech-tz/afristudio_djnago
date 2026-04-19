from django.urls import path
from apps.accounts.views import AddressListCreateView, AddressDetailView, AddressSetDefaultView

urlpatterns = [
    path('',              AddressListCreateView.as_view(), name='address-list'),
    path('<int:pk>/',     AddressDetailView.as_view(),     name='address-detail'),
    path('<int:pk>/set-default/', AddressSetDefaultView.as_view(), name='address-set-default'),
]
