from django.urls import re_path
from .consumers import AuctionConsumer

websocket_urlpatterns = [
    re_path(r'^ws/auctions/(?P<auction_uuid>[0-9a-f-]+)/$', AuctionConsumer.as_asgi()),
]
