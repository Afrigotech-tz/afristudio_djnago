from django.urls import path
from apps.artworks.views import (
    ArtworkListCreateView,
    ArtworkDetailView,
    ArtworkImageListCreateView,
    ArtworkImageDetailView,
)

urlpatterns = [
    path('', ArtworkListCreateView.as_view(), name='artwork-list'),
    path('<uuid:uuid>/', ArtworkDetailView.as_view(), name='artwork-detail'),
    path('<uuid:uuid>/images/', ArtworkImageListCreateView.as_view(), name='artwork-images'),
    path('<uuid:uuid>/images/<int:pk>/', ArtworkImageDetailView.as_view(), name='artwork-image-detail'),
    path('<uuid:uuid>/images/<int:pk>/set-primary/', ArtworkImageDetailView.as_view(), name='artwork-image-set-primary'),
]
