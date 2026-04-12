from django.urls import path
from .views import AuctionListCreateView, AuctionDetailView, AuctionStartView, AuctionEndView, PlaceBidView

urlpatterns = [
    path('', AuctionListCreateView.as_view(), name='auction-list-create'),
    path('<uuid:uuid>/', AuctionDetailView.as_view(), name='auction-detail'),
    path('<uuid:uuid>/start/', AuctionStartView.as_view(), name='auction-start'),
    path('<uuid:uuid>/end/', AuctionEndView.as_view(), name='auction-end'),
    path('<uuid:uuid>/bid/', PlaceBidView.as_view(), name='auction-bid'),
]
