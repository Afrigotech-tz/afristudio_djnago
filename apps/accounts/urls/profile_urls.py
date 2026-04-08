from django.urls import path
from apps.accounts.views import ProfileView, RemoveAvatarView

urlpatterns = [
    path('', ProfileView.as_view(), name='profile'),
    path('avatar', RemoveAvatarView.as_view(), name='profile-avatar'),
]
