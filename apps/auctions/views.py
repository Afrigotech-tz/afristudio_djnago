"""
auctions/views.py

POST   /api/auctions/                    — create auction (artist/admin)
GET    /api/auctions/                    — list all auctions
GET    /api/auctions/<uuid>/             — auction detail + bids
POST   /api/auctions/<uuid>/start/       — go live
POST   /api/auctions/<uuid>/end/         — end auction manually
POST   /api/auctions/<uuid>/bid/         — place a bid (authenticated users)
"""

import json
from django.db import transaction, IntegrityError
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework import status
from drf_spectacular.utils import extend_schema, OpenApiResponse

from .models import Auction, Bid, close_auction
from .serializers import AuctionSerializer, CreateAuctionSerializer, UpdateAuctionSerializer, PlaceBidSerializer, BidSerializer
from apps.activity_logs.utils import log_activity
from apps.wallet.models import Wallet, WalletTransaction


def _broadcast(auction_uuid, data: dict):
    """Broadcast a message to all WebSocket clients watching this auction."""
    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                f'auction_{auction_uuid}',
                {'type': 'auction_update', 'data': data},
            )
    except Exception:
        pass  # channels not configured — skip broadcast silently


class AuctionListCreateView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]

    @extend_schema(tags=['Auctions'], summary='List all auctions', responses={200: AuctionSerializer(many=True)})
    def get(self, request):
        qs = Auction.objects.select_related('artwork', 'created_by', 'winner').all()
        status_filter = request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        return Response(AuctionSerializer(qs, many=True, context={'request': request}).data)

    @extend_schema(tags=['Auctions'], summary='Create an auction for an artwork',
                   request=CreateAuctionSerializer, responses={201: AuctionSerializer})
    def post(self, request):
        serializer = CreateAuctionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        from apps.artworks.models import Artwork
        artwork = get_object_or_404(Artwork, uuid=data['artwork_uuid'])

        if artwork.is_sold:
            return Response({'message': 'This artwork has already been sold.'}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        if hasattr(artwork, 'auction'):
            existing = artwork.auction
            if existing.status in (Auction.STATUS_PENDING, Auction.STATUS_LIVE):
                return Response(
                    {'message': 'This artwork already has an active auction.'},
                    status=status.HTTP_422_UNPROCESSABLE_ENTITY,
                )
            # ended auctions also hold the unique slot — one auction per artwork
            return Response(
                {'message': 'This artwork has already been auctioned. Each artwork can only be auctioned once.'},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        try:
            auction = Auction.objects.create(
                artwork=artwork,
                created_by=request.user,
                start_price=data['start_price'],
                reserve_price=data.get('reserve_price'),
                current_price=data['start_price'],
                bid_increment=data['bid_increment'],
                currency=data['currency'],
                start_time=data['start_time'],
                end_time=data['end_time'],
            )
        except IntegrityError:
            return Response(
                {'message': 'This artwork is already linked to an auction.'},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        log_activity(user=request.user, subject=auction,
                     description=f'Created auction for "{artwork.name}"',
                     log_name='auctions', event='auction_created')

        return Response(AuctionSerializer(auction, context={'request': request}).data, status=status.HTTP_201_CREATED)


class AuctionDetailView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]

    def _get_auction(self, uuid):
        return get_object_or_404(
            Auction.objects.select_related('artwork', 'created_by', 'winner'),
            uuid=uuid,
        )

    @extend_schema(tags=['Auctions'], summary='Get auction detail', responses={200: AuctionSerializer})
    def get(self, request, uuid):
        auction = self._get_auction(uuid)
        auction.check_and_auto_close()
        return Response(AuctionSerializer(auction, context={'request': request}).data)

    @extend_schema(
        tags=['Auctions'],
        summary='Update a pending auction',
        request=UpdateAuctionSerializer,
        responses={200: AuctionSerializer, 422: OpenApiResponse(description='Auction is not pending.')},
    )
    def patch(self, request, uuid):
        if not (request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser or request.user.has_perm('auctions.change_auction'))):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied()
        auction = self._get_auction(uuid)
        if auction.status != Auction.STATUS_PENDING:
            return Response({'message': 'Only pending auctions can be edited.'}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        serializer = UpdateAuctionSerializer(auction, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        for field, value in serializer.validated_data.items():
            setattr(auction, field, value)
        auction.save()
        auction.refresh_from_db()
        return Response(AuctionSerializer(auction, context={'request': request}).data)

    @extend_schema(
        tags=['Auctions'],
        summary='Delete a pending auction',
        responses={204: None, 422: OpenApiResponse(description='Auction is not pending.')},
    )
    def delete(self, request, uuid):
        if not (request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser or request.user.has_perm('auctions.delete_auction'))):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied()
        auction = self._get_auction(uuid)
        if auction.status != Auction.STATUS_PENDING:
            return Response({'message': 'Only pending auctions can be deleted.'}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        log_activity(user=request.user, subject=None,
                     description=f'Deleted pending auction for "{auction.artwork.name}"',
                     log_name='auctions', event='auction_deleted')
        auction.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AuctionStartView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Auctions'], summary='Start an auction (go live)',
                   responses={200: AuctionSerializer, 422: OpenApiResponse(description='Auction not pending.')})
    def post(self, request, uuid):
        auction = get_object_or_404(Auction, uuid=uuid)

        if auction.status != Auction.STATUS_PENDING:
            return Response({'message': 'Only pending auctions can be started.'}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        auction.status = Auction.STATUS_LIVE
        auction.start_time = timezone.now()
        auction.save(update_fields=['status', 'start_time', 'updated_at'])

        _broadcast(auction.uuid, {
            'event': 'auction_started',
            'auction_uuid': str(auction.uuid),
            'artwork_name': auction.artwork.name,
            'start_price': str(auction.start_price),
            'end_time': auction.end_time.isoformat(),
        })

        log_activity(user=request.user, subject=auction,
                     description=f'Started auction for "{auction.artwork.name}"',
                     log_name='auctions', event='auction_started')

        return Response(AuctionSerializer(auction, context={'request': request}).data)


class AuctionEndView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Auctions'], summary='Manually end a live auction',
                   responses={200: AuctionSerializer, 422: OpenApiResponse(description='Auction not live.')})
    def post(self, request, uuid):
        auction = get_object_or_404(Auction, uuid=uuid)

        if auction.status != Auction.STATUS_LIVE:
            return Response({'message': 'Only live auctions can be ended.'}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        close_auction(auction)

        winner_name = auction.winner.name if auction.winner else None
        _broadcast(auction.uuid, {
            'event': 'auction_ended',
            'auction_uuid': str(auction.uuid),
            'winner': winner_name,
            'final_price': str(auction.current_price),
            'currency': auction.currency,
        })

        return Response(AuctionSerializer(auction, context={'request': request}).data)


class PlaceBidView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['Auctions'],
        summary='Place a bid on a live auction',
        request=PlaceBidSerializer,
        responses={
            201: BidSerializer,
            400: OpenApiResponse(description='Bid too low or auction not live.'),
            402: OpenApiResponse(description='Insufficient wallet balance.'),
        },
    )
    def post(self, request, uuid):
        auction = get_object_or_404(
            Auction.objects.select_related('artwork'),
            uuid=uuid,
        )

        # Auto-close if expired
        if auction.check_and_auto_close():
            return Response({'message': 'This auction has already ended.'}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        if not auction.is_live:
            return Response({'message': 'This auction is not currently live.'}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        serializer = PlaceBidSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        bid_amount = serializer.validated_data['amount']

        if bid_amount < auction.minimum_next_bid:
            return Response(
                {'message': f'Bid must be at least {auction.minimum_next_bid} {auction.currency}.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if auction.winner == request.user:
            return Response({'message': 'You are already the highest bidder.'}, status=status.HTTP_400_BAD_REQUEST)

        # Pre-flight balance check (quick, outside transaction — gives early feedback)
        pre_wallet, _ = Wallet.objects.get_or_create(user=request.user)
        pre_wallet.refresh_from_db()
        if not pre_wallet.can_afford(bid_amount):
            return Response(
                {
                    'message': (
                        f'Insufficient wallet balance. '
                        f'Your balance is {pre_wallet.balance} {pre_wallet.currency}, '
                        f'but the bid requires {bid_amount} {auction.currency}.'
                    )
                },
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )

        with transaction.atomic():
            # Re-fetch wallet with a row-level lock to get the definitive fresh balance
            try:
                wallet = Wallet.objects.select_for_update().get(user=request.user)
            except Wallet.DoesNotExist:
                wallet = Wallet.objects.create(user=request.user)

            # Re-validate balance inside the lock (prevents race conditions)
            if not wallet.can_afford(bid_amount):
                return Response(
                    {
                        'message': (
                            f'Insufficient wallet balance. '
                            f'Your balance is {wallet.balance} {wallet.currency}, '
                            f'but the bid requires {bid_amount} {auction.currency}.'
                        )
                    },
                    status=status.HTTP_402_PAYMENT_REQUIRED,
                )

            # Refund previous highest bidder
            prev_winning_bid = auction.bids.filter(is_winning=True).select_related('bidder').first()
            if prev_winning_bid:
                prev_winning_bid.is_winning = False
                prev_winning_bid.save(update_fields=['is_winning'])
                try:
                    prev_wallet = Wallet.objects.select_for_update().get(user=prev_winning_bid.bidder)
                except Wallet.DoesNotExist:
                    prev_wallet = Wallet.objects.create(user=prev_winning_bid.bidder)
                prev_wallet.credit(
                    amount=prev_winning_bid.amount,
                    description=f'Refund — outbid on "{auction.artwork.name}"',
                    reference=str(prev_winning_bid.uuid),
                    tx_type=WalletTransaction.TYPE_REFUND,
                )

            # Deduct from bidder's wallet (wallet is fresh & locked — no stale data)
            wallet.deduct(
                amount=bid_amount,
                description=f'Bid on "{auction.artwork.name}"',
                reference=str(auction.uuid),
            )

            # Create new winning bid
            bid = Bid.objects.create(
                auction=auction,
                bidder=request.user,
                amount=bid_amount,
                is_winning=True,
            )

            # Update auction
            auction.current_price = bid_amount
            auction.winner = request.user
            auction.total_bids += 1
            auction.save(update_fields=['current_price', 'winner', 'total_bids', 'updated_at'])

        log_activity(
            user=request.user,
            subject=auction,
            description=f'Placed bid of {bid_amount} {auction.currency} on "{auction.artwork.name}"',
            log_name='auctions',
            event='bid_placed',
        )

        _broadcast(auction.uuid, {
            'event': 'bid_placed',
            'bidder': request.user.name,
            'amount': str(bid_amount),
            'currency': auction.currency,
            'current_price': str(auction.current_price),
            'minimum_next_bid': str(auction.minimum_next_bid),
            'total_bids': auction.total_bids,
            'seconds_remaining': max(int((auction.end_time - timezone.now()).total_seconds()), 0),
        })

        return Response(BidSerializer(bid).data, status=status.HTTP_201_CREATED)
