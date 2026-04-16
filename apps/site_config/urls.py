from django.urls import path
from .views import (
    LandingHeroView,
    HeroContentView,
    ContactInfoView,
    ContactMessageCreateView,
    ContactMessageListView,
    ContactMessageUnreadCountView,
    ContactMessageStatusView,
)

urlpatterns = [
    # Landing hero image
    path('hero/', LandingHeroView.as_view(), name='site-hero'),

    # Landing hero text content
    path('hero-content/', HeroContentView.as_view(), name='site-hero-content'),

    # Contact information (email / phone / location)
    path('contact-info/', ContactInfoView.as_view(), name='site-contact-info'),

    # Contact form submission (public)
    path('contact/', ContactMessageCreateView.as_view(), name='site-contact-submit'),

    # Admin: unread message count
    path('contact/messages/unread-count/', ContactMessageUnreadCountView.as_view(), name='site-contact-unread-count'),

    # Admin: list all messages
    path('contact/messages/', ContactMessageListView.as_view(), name='site-contact-messages'),

    # Admin: update a message status
    path('contact/messages/<int:pk>/status/', ContactMessageStatusView.as_view(), name='site-contact-message-status'),
]
