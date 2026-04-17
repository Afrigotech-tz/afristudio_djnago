from decimal import Decimal
from rest_framework import serializers
from .models import Wallet, WalletTransaction


class WalletTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = WalletTransaction
        fields = ['id', 'type', 'amount', 'balance_after', 'description', 'reference', 'created_at']


class WalletSerializer(serializers.ModelSerializer):
    transactions = WalletTransactionSerializer(many=True, read_only=True)

    class Meta:
        model = Wallet
        fields = ['id', 'balance', 'currency', 'transactions', 'updated_at']


class DepositSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=15, decimal_places=2, min_value=Decimal('1.00'))
    description = serializers.CharField(max_length=255, required=False, default='Manual deposit')


class AdminWalletSerializer(serializers.ModelSerializer):
    user_name  = serializers.CharField(source='user.name',  read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    user_uuid  = serializers.UUIDField(source='user.uuid',  read_only=True)

    class Meta:
        model = Wallet
        fields = ['id', 'user_uuid', 'user_name', 'user_email', 'balance', 'currency', 'updated_at']
