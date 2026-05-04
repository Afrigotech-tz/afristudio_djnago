from django.urls import path
from .views import (
    LandingHeroView,
    LandingFaviconView,
    HeroContentView,
    ContactInfoView,
    LanguageConfigView,
    ContactMessageCreateView,
    ContactMessageListView,
    ContactMessageUnreadCountView,
    ContactMessageStatusView,
    ContactMessageDeleteView,
    ArtistProfileView,
    ExhibitionListCreateView,
    ExhibitionDetailView,
)

urlpatterns = [
    path('hero/', LandingHeroView.as_view(), name='site-hero'),
    path('favicon/', LandingFaviconView.as_view(), name='site-favicon'),
    path('hero-content/', HeroContentView.as_view(), name='site-hero-content'),
    path('contact-info/', ContactInfoView.as_view(), name='site-contact-info'),
    path('languages/', LanguageConfigView.as_view(), name='site-languages'),
    path('contact/', ContactMessageCreateView.as_view(), name='site-contact-submit'),
    path('contact/messages/unread-count/', ContactMessageUnreadCountView.as_view(), name='site-contact-unread-count'),
    path('contact/messages/', ContactMessageListView.as_view(), name='site-contact-messages'),
    path('contact/messages/<int:pk>/status/', ContactMessageStatusView.as_view(), name='site-contact-message-status'),
    path('contact/messages/<int:pk>/', ContactMessageDeleteView.as_view(), name='site-contact-message-delete'),

    # Artist profile & exhibitions
    path('artist/', ArtistProfileView.as_view(), name='site-artist-profile'),
    path('exhibitions/', ExhibitionListCreateView.as_view(), name='site-exhibitions'),
    path('exhibitions/<int:pk>/', ExhibitionDetailView.as_view(), name='site-exhibition-detail'),
]
