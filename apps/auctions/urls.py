from django.urls import path
from .views import (
    AuctionListCreateView, AuctionDetailView, AuctionStartView, AuctionEndView,
    PlaceBidView, AuctionConfigView, AuctionWinnersView, AuctionWinnerMarkPaidView,
    AuctionViolationsView, AuctionViolationBanView,
    AuctionImageListCreateView, AuctionImageDetailView,
)

urlpatterns = [
    path('', AuctionListCreateView.as_view(), name='auction-list-create'),
    path('<uuid:uuid>/', AuctionDetailView.as_view(), name='auction-detail'),
    path('<uuid:uuid>/start/', AuctionStartView.as_view(), name='auction-start'),
    path('<uuid:uuid>/end/', AuctionEndView.as_view(), name='auction-end'),
    path('<uuid:uuid>/bid/', PlaceBidView.as_view(), name='auction-bid'),

    # Images
    path('<uuid:uuid>/images/', AuctionImageListCreateView.as_view(), name='auction-images'),
    path('<uuid:uuid>/images/<int:pk>/', AuctionImageDetailView.as_view(), name='auction-image-detail'),
    path('<uuid:uuid>/images/<int:pk>/set-primary/', AuctionImageDetailView.as_view(), name='auction-image-set-primary'),

    # Admin: configuration
    path('config/', AuctionConfigView.as_view(), name='auction-config'),

    # Admin: winner records
    path('winners/', AuctionWinnersView.as_view(), name='auction-winners'),
    path('winners/<int:pk>/mark-paid/', AuctionWinnerMarkPaidView.as_view(), name='auction-winner-mark-paid'),

    # Admin: violations
    path('violations/', AuctionViolationsView.as_view(), name='auction-violations'),
    path('violations/<int:pk>/ban/', AuctionViolationBanView.as_view(), name='auction-violation-ban'),
]
