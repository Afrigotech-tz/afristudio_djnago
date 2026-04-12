"""
auctions/consumers.py
WebSocket consumer — every client watching an auction connects here.

Connect:  ws://host/ws/auctions/<auction_uuid>/
          Optional JWT auth: ws://host/ws/auctions/<uuid>/?token=<access_token>

Events pushed to clients:
  auction_started  — auction went live
  bid_placed       — new bid was placed
  auction_ended    — auction finished (includes winner & final price)
  ping             — server heartbeat every 30 s
"""

import json
from urllib.parse import parse_qs
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async


class AuctionConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.auction_uuid = self.scope['url_route']['kwargs']['auction_uuid']
        self.group_name = f'auction_{self.auction_uuid}'

        # Optional JWT identification (read-only auth — bidding is via REST)
        token = self._get_token_from_scope()
        self.auth_user = await self._get_user(token) if token else None

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # Send current auction snapshot on connect
        snapshot = await self._get_auction_snapshot(self.auction_uuid)
        if snapshot:
            await self.send(text_data=json.dumps({'event': 'snapshot', **snapshot}))
        else:
            await self.close(code=4004)

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        """Clients may send a ping to keep the connection alive."""
        try:
            data = json.loads(text_data)
            if data.get('type') == 'ping':
                await self.send(text_data=json.dumps({'event': 'pong'}))
        except (json.JSONDecodeError, Exception):
            pass

    # ── Group message handler (called by REST views via channel_layer.group_send) ──

    async def auction_update(self, event):
        """Forward any group broadcast to this WebSocket client."""
        await self.send(text_data=json.dumps(event['data']))

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_token_from_scope(self):
        qs = parse_qs(self.scope.get('query_string', b'').decode())
        tokens = qs.get('token', [])
        return tokens[0] if tokens else None

    @database_sync_to_async
    def _get_user(self, token: str):
        try:
            from rest_framework_simplejwt.tokens import AccessToken
            from django.contrib.auth import get_user_model
            payload = AccessToken(token)
            User = get_user_model()
            return User.objects.get(id=payload['user_id'])
        except Exception:
            return None

    @database_sync_to_async
    def _get_auction_snapshot(self, auction_uuid: str):
        from .models import Auction
        try:
            auction = Auction.objects.select_related('artwork', 'winner').get(uuid=auction_uuid)
            from django.utils import timezone
            return {
                'auction_uuid': str(auction.uuid),
                'artwork_name': auction.artwork.name,
                'status': auction.status,
                'current_price': str(auction.current_price),
                'minimum_next_bid': str(auction.minimum_next_bid),
                'currency': auction.currency,
                'total_bids': auction.total_bids,
                'end_time': auction.end_time.isoformat(),
                'seconds_remaining': max(int((auction.end_time - timezone.now()).total_seconds()), 0),
                'winner': auction.winner.name if auction.winner else None,
            }
        except Auction.DoesNotExist:
            return None
