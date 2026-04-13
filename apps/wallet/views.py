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

from .models import Wallet, WalletTransaction
from .serializers import WalletSerializer, DepositSerializer


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
