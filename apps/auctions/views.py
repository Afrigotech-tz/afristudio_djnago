"""
auctions/views.py

POST   /api/auctions/                       — create auction
GET    /api/auctions/                       — list auctions
GET    /api/auctions/<uuid>/                — detail + bids
PATCH  /api/auctions/<uuid>/                — update pending auction
DELETE /api/auctions/<uuid>/                — delete pending auction
POST   /api/auctions/<uuid>/start/          — go live
POST   /api/auctions/<uuid>/end/            — end manually
POST   /api/auctions/<uuid>/bid/            — place bid

GET/PATCH /api/auctions/config/             — payment rules (admin)
GET       /api/auctions/winners/            — all winner records (admin)
GET       /api/auctions/violations/         — payment violations (admin)
POST      /api/auctions/violations/<id>/ban/ — ban violating user (admin)
"""

import json
from django.db import transaction, IntegrityError
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly, IsAdminUser
from rest_framework import status
from drf_spectacular.utils import extend_schema, OpenApiResponse

from .models import Auction, Bid, AuctionConfig, AuctionWinner, AuctionPaymentViolation, close_auction
from .serializers import (
    AuctionSerializer, CreateAuctionSerializer, UpdateAuctionSerializer, ExtendAuctionSerializer,
    PlaceBidSerializer, BidSerializer,
    AuctionConfigSerializer, AuctionWinnerSerializer, AuctionPaymentViolationSerializer,
)
from apps.activity_logs.utils import log_activity
from apps.wallet.models import Wallet, WalletTransaction


def _broadcast(auction_uuid, data: dict):
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
        pass


# ── List / Create ──────────────────────────────────────────────────────────────

class AuctionListCreateView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request):
        qs = Auction.objects.select_related('artwork', 'created_by', 'winner').all()
        status_filter = request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        return Response(AuctionSerializer(qs, many=True, context={'request': request}).data)

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
            # Ended auction — block unless the ending was due to non-payment (relisted)
            if existing.status == Auction.STATUS_ENDED:
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


# ── Detail / Update / Delete ──────────────────────────────────────────────────

class AuctionDetailView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]

    def _get_auction(self, uuid):
        return get_object_or_404(
            Auction.objects.select_related('artwork', 'created_by', 'winner'),
            uuid=uuid,
        )

    def get(self, request, uuid):
        auction = self._get_auction(uuid)
        auction.check_and_auto_close()
        return Response(AuctionSerializer(auction, context={'request': request}).data)

    def patch(self, request, uuid):
        if not (request.user.is_authenticated and (
            request.user.is_staff or request.user.is_superuser
            or request.user.has_perm('auctions.change_auction')
        )):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied()
        auction = self._get_auction(uuid)

        if auction.status == Auction.STATUS_LIVE:
            # Live auctions: only end_time and bid_increment can be changed
            serializer = ExtendAuctionSerializer(auction, data=request.data)
            serializer.is_valid(raise_exception=True)
            for field, value in serializer.validated_data.items():
                setattr(auction, field, value)
            update_fields = list(serializer.validated_data.keys()) + ['updated_at']
            auction.save(update_fields=update_fields)
            log_activity(
                user=request.user, subject=auction,
                description=f'Updated live auction for "{auction.artwork.name}" — new end: {auction.end_time}',
                log_name='auctions', event='auction_extended',
            )
            _broadcast(auction.uuid, {
                'event': 'auction_extended',
                'auction_uuid': str(auction.uuid),
                'end_time': auction.end_time.isoformat(),
                'bid_increment': str(auction.bid_increment),
            })
            auction.refresh_from_db()
            return Response(AuctionSerializer(auction, context={'request': request}).data)

        if auction.status != Auction.STATUS_PENDING:
            return Response(
                {'message': 'Cancelled auctions cannot be edited.'},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        serializer = UpdateAuctionSerializer(auction, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        for field, value in serializer.validated_data.items():
            setattr(auction, field, value)
        auction.save()
        auction.refresh_from_db()
        return Response(AuctionSerializer(auction, context={'request': request}).data)

    def delete(self, request, uuid):
        if not (request.user.is_authenticated and (
            request.user.is_staff or request.user.is_superuser
            or request.user.has_perm('auctions.delete_auction')
        )):
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


# ── Start / End ───────────────────────────────────────────────────────────────

class AuctionStartView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, uuid):
        auction = get_object_or_404(Auction, uuid=uuid)
        if auction.status != Auction.STATUS_PENDING:
            return Response({'message': 'Only pending auctions can be started.'}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        auction.status     = Auction.STATUS_LIVE
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


# ── Place Bid ─────────────────────────────────────────────────────────────────

class PlaceBidView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, uuid):
        auction = get_object_or_404(Auction.objects.select_related('artwork'), uuid=uuid)

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

        # Check if user has outstanding unpaid violations → could block bidding
        config = AuctionConfig.get_config()
        violation_count = AuctionPaymentViolation.objects.filter(user=request.user).count()
        if violation_count >= config.max_violations:
            return Response(
                {
                    'message': (
                        f'Your bidding privileges have been suspended due to '
                        f'{violation_count} unpaid auction win(s). '
                        f'Please contact support.'
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # ── Bidding logic branches by payment mode ────────────────────────────

        if config.payment_mode == AuctionConfig.MODE_FREE_BID:
            # No wallet ops — just record the bid
            with transaction.atomic():
                auction.bids.filter(is_winning=True).update(is_winning=False)
                bid = Bid.objects.create(
                    auction=auction,
                    bidder=request.user,
                    amount=bid_amount,
                    is_winning=True,
                )
                auction.current_price = bid_amount
                auction.winner        = request.user
                auction.total_bids   += 1
                auction.save(update_fields=['current_price', 'winner', 'total_bids', 'updated_at'])

        elif config.payment_mode == AuctionConfig.MODE_BALANCE_REQUIRED:
            # Check balance but do NOT deduct — funds stay in wallet until checkout
            wallet, _ = Wallet.objects.get_or_create(user=request.user)
            wallet.refresh_from_db()
            if not wallet.can_afford(bid_amount):
                return Response(
                    {
                        'message': (
                            f'Insufficient wallet balance. '
                            f'Your balance is {wallet.balance} {wallet.currency}, '
                            f'but the bid requires {bid_amount} {auction.currency}. '
                            f'Please top up your wallet before bidding.'
                        )
                    },
                    status=status.HTTP_402_PAYMENT_REQUIRED,
                )
            with transaction.atomic():
                auction.bids.filter(is_winning=True).update(is_winning=False)
                bid = Bid.objects.create(
                    auction=auction,
                    bidder=request.user,
                    amount=bid_amount,
                    is_winning=True,
                )
                auction.current_price = bid_amount
                auction.winner        = request.user
                auction.total_bids   += 1
                auction.save(update_fields=['current_price', 'winner', 'total_bids', 'updated_at'])

        else:
            # MODE_AUTO_DEDUCT — current behaviour: deduct on bid, refund outbid
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
                wallet = Wallet.objects.select_for_update().get(user=request.user)
                if not wallet.can_afford(bid_amount):
                    return Response(
                        {'message': f'Insufficient wallet balance ({wallet.balance} {wallet.currency}).'},
                        status=status.HTTP_402_PAYMENT_REQUIRED,
                    )

                # Refund previous winning bidder
                prev_bid = auction.bids.filter(is_winning=True).select_related('bidder').first()
                if prev_bid:
                    prev_bid.is_winning = False
                    prev_bid.save(update_fields=['is_winning'])
                    try:
                        prev_wallet = Wallet.objects.select_for_update().get(user=prev_bid.bidder)
                    except Wallet.DoesNotExist:
                        prev_wallet = Wallet.objects.create(user=prev_bid.bidder)
                    prev_wallet.credit(
                        amount=prev_bid.amount,
                        description=f'Refund — outbid on "{auction.artwork.name}"',
                        reference=str(prev_bid.uuid),
                        tx_type=WalletTransaction.TYPE_REFUND,
                    )

                wallet.deduct(
                    amount=bid_amount,
                    description=f'Bid on "{auction.artwork.name}"',
                    reference=str(auction.uuid),
                )
                bid = Bid.objects.create(
                    auction=auction,
                    bidder=request.user,
                    amount=bid_amount,
                    is_winning=True,
                )
                auction.current_price = bid_amount
                auction.winner        = request.user
                auction.total_bids   += 1
                auction.save(update_fields=['current_price', 'winner', 'total_bids', 'updated_at'])

        log_activity(
            user=request.user, subject=auction,
            description=f'Placed bid of {bid_amount} {auction.currency} on "{auction.artwork.name}"',
            log_name='auctions', event='bid_placed',
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


# ── Auction Config (admin) ────────────────────────────────────────────────────

class AuctionConfigView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        config = AuctionConfig.get_config()
        return Response(AuctionConfigSerializer(config).data)

    def patch(self, request):
        config = AuctionConfig.get_config()
        serializer = AuctionConfigSerializer(config, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        log_activity(
            user=request.user, subject=None,
            description='Updated auction payment configuration',
            log_name='auctions', event='config_updated',
        )
        return Response(AuctionConfigSerializer(config).data)


# ── Winners (admin) ───────────────────────────────────────────────────────────

class AuctionWinnersView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        qs = (
            AuctionWinner.objects
            .select_related('user', 'auction', 'auction__artwork', 'order')
            .all()
        )
        payment_status = request.query_params.get('payment_status')
        if payment_status:
            qs = qs.filter(payment_status=payment_status)
        return Response(AuctionWinnerSerializer(qs, many=True).data)


# ── Mark Winner Paid (admin) ──────────────────────────────────────────────────

class AuctionWinnerMarkPaidView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        winner = get_object_or_404(AuctionWinner, pk=pk)
        if winner.payment_status == AuctionWinner.PAYMENT_PAID:
            return Response({'message': 'Already marked as paid.'}, status=status.HTTP_400_BAD_REQUEST)
        winner.payment_status = AuctionWinner.PAYMENT_PAID
        winner.paid_at = timezone.now()
        winner.save(update_fields=['payment_status', 'paid_at'])
        log_activity(
            user=request.user, subject=None,
            description=f'Manually marked auction winner (id={pk}) as paid',
            log_name='auctions', event='winner_marked_paid',
        )
        return Response(AuctionWinnerSerializer(winner).data)


# ── Violations (admin) ────────────────────────────────────────────────────────

class AuctionViolationsView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        qs = (
            AuctionPaymentViolation.objects
            .select_related('user', 'auction_winner', 'auction_winner__auction', 'auction_winner__auction__artwork')
            .all()
        )
        return Response(AuctionPaymentViolationSerializer(qs, many=True).data)


class AuctionViolationBanView(APIView):
    """Manually ban a user from bidding based on their violations."""
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        violation = get_object_or_404(AuctionPaymentViolation, pk=pk)
        user = violation.user
        config = AuctionConfig.get_config()

        total = AuctionPaymentViolation.objects.filter(user=user).count()

        log_activity(
            user=request.user, subject=None,
            description=(
                f'Manually reviewed violation for {user.name} — '
                f'{total} total violation(s). '
                f'Max allowed: {config.max_violations}.'
            ),
            log_name='auctions', event='violation_reviewed',
        )
        return Response({
            'user': user.name,
            'total_violations': total,
            'bidding_suspended': total >= config.max_violations,
            'max_violations': config.max_violations,
        })
