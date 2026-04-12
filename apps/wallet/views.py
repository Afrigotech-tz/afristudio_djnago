"""
wallet/views.py
GET  /api/wallet/              — get balance + transaction history
POST /api/wallet/deposit/      — top up balance (admin-only in production; open for dev)
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from drf_spectacular.utils import extend_schema, OpenApiResponse

from .models import Wallet
from .serializers import WalletSerializer, DepositSerializer
from apps.wallet.models import WalletTransaction


class WalletView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['Wallet'],
        summary='Get wallet balance and transactions',
        responses={200: WalletSerializer},
    )
    def get(self, request):
        wallet, _ = Wallet.objects.get_or_create(user=request.user)
        return Response(WalletSerializer(wallet).data)


class WalletDepositView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['Wallet'],
        summary='Deposit funds into wallet',
        request=DepositSerializer,
        responses={200: WalletSerializer},
    )
    def post(self, request):
        serializer = DepositSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        wallet, _ = Wallet.objects.get_or_create(user=request.user)
        wallet.credit(
            amount=data['amount'],
            description=data['description'],
            tx_type=WalletTransaction.TYPE_DEPOSIT,
        )
        return Response(WalletSerializer(wallet).data)
