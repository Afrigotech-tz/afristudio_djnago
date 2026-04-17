from django.urls import path
from . import views

urlpatterns = [
    path('auctions/',          views.AuctionsReportView.as_view(),          name='report-auctions'),
    path('artworks/sold/',     views.SoldArtworksReportView.as_view(),      name='report-artworks-sold'),
    path('artworks/available/',views.AvailableArtworksReportView.as_view(), name='report-artworks-available'),
    path('sales/',             views.SalesReportView.as_view(),             name='report-sales'),
]
