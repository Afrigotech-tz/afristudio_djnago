from django.urls import path
from apps.artworks.views import ArtworkListCreateView, ArtworkDetailView

urlpatterns = [
    path('', ArtworkListCreateView.as_view(), name='artwork-list'),
    path('<uuid:uuid>/', ArtworkDetailView.as_view(), name='artwork-detail'),
]
