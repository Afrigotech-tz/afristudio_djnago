from django.urls import path
from apps.artworks.views import CategoryListCreateView, CategoryDetailView

urlpatterns = [
    path('', CategoryListCreateView.as_view(), name='category-list'),
    path('<uuid:uuid>/', CategoryDetailView.as_view(), name='category-detail'),
]
