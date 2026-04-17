"""
wallet/views.py
GET  /api/wallet/              — get balance + transaction history
POST /api/wallet/deposit/      — top up balance
"""

from django.db import transaction as db_transaction
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from drf_spectacular.utils import extend_schema, OpenApiResponse

from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAdminUser
from .models import Wallet, WalletTransaction
from .serializers import WalletSerializer, DepositSerializer, AdminWalletSerializer


def _get_or_create_wallet(user):
    """Always return the wallet for a user, creating it if it doesn't exist."""
    wallet, _ = Wallet.objects.get_or_create(user=user)
    return wallet


def _get_wallet_locked(user):
    """Fetch wallet with a row-level lock inside an atomic block. Creates if missing."""
    try:
        return Wallet.objects.select_for_update().get(user=user)
    except Wallet.DoesNotExist:
        return Wallet.objects.create(user=user)


class WalletView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['Wallet'],
        summary='Get wallet balance and transactions',
        responses={200: WalletSerializer},
    )
    def get(self, request):
        wallet = _get_or_create_wallet(request.user)
        # Refresh from DB to guarantee the latest balance
        wallet.refresh_from_db()
        return Response(WalletSerializer(wallet).data)


class WalletDepositView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['Wallet'],
        summary='Deposit funds into wallet',
        request=DepositSerializer,
        responses={201: WalletSerializer},
    )
    def post(self, request):
        serializer = DepositSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        with db_transaction.atomic():
            wallet = _get_wallet_locked(request.user)
            wallet.credit(
                amount=data['amount'],
                description=data.get('description', 'Manual deposit'),
                tx_type=WalletTransaction.TYPE_DEPOSIT,
            )

        wallet.refresh_from_db()
        return Response(WalletSerializer(wallet).data, status=status.HTTP_201_CREATED)


# ──────────────────────────────────────────────
# Admin wallet management
# ──────────────────────────────────────────────

class AdminWalletListView(APIView):
    """GET /api/admin/wallets/ — list all user wallets (admin only)"""
    permission_classes = [IsAdminUser]

    @extend_schema(tags=['Admin'], summary='List all user wallets', responses={200: AdminWalletSerializer(many=True)})
    def get(self, request):
        qs = Wallet.objects.select_related('user').all().order_by('-balance')
        search = request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(Q(user__name__icontains=search) | Q(user__email__icontains=search))
        return Response(AdminWalletSerializer(qs, many=True).data)


class AdminWalletCreditView(APIView):
    """POST /api/admin/wallets/<id>/credit/ — credit a user's wallet (admin only)"""
    permission_classes = [IsAdminUser]

    @extend_schema(
        tags=['Admin'],
        summary='Credit a user wallet',
        request=DepositSerializer,
        responses={200: AdminWalletSerializer},
    )
    def post(self, request, pk):
        get_object_or_404(Wallet, pk=pk)  # 404 check
        serializer = DepositSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        with db_transaction.atomic():
            wallet = Wallet.objects.select_for_update().get(pk=pk)
            wallet.credit(
                amount=data['amount'],
                description=data.get('description', 'Admin credit'),
                tx_type=WalletTransaction.TYPE_DEPOSIT,
            )
        wallet.refresh_from_db()
        return Response(AdminWalletSerializer(wallet).data)
