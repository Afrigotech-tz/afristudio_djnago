from rest_framework import serializers
from .models import PaymentMethod, PaymentTransaction


# ── PaymentMethod ──────────────────────────────────────────────────────────────

class PaymentMethodPublicSerializer(serializers.ModelSerializer):
    """Returned to users — no secret keys."""
    public_config = serializers.SerializerMethodField()

    class Meta:
        model  = PaymentMethod
        fields = ['channel', 'display_name', 'description', 'sort_order', 'public_config']

    def get_public_config(self, obj):
        if obj.channel == PaymentMethod.CHANNEL_BANK:
            cfg = obj.config
            return {
                'bank_name':       cfg.get('bank_name', ''),
                'account_number':  cfg.get('account_number', ''),
                'account_name':    cfg.get('account_name', ''),
                'branch':          cfg.get('branch', ''),
                'swift_code':      cfg.get('swift_code', ''),
                'instructions':    cfg.get('instructions', ''),
            }
        if obj.channel == PaymentMethod.CHANNEL_STRIPE:
            return {'publishable_key': obj.config.get('publishable_key', '')}
        return {}


class PaymentMethodAdminSerializer(serializers.ModelSerializer):
    """Full serializer for admin — includes sensitive config."""
    class Meta:
        model  = PaymentMethod
        fields = ['id', 'channel', 'display_name', 'description',
                  'is_active', 'sort_order', 'config', 'updated_at']
        read_only_fields = ['channel', 'updated_at']


# ── PaymentTransaction ─────────────────────────────────────────────────────────

class PaymentTransactionSerializer(serializers.ModelSerializer):
    user_name  = serializers.CharField(source='user.name',  read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    order_uuid = serializers.UUIDField(source='order.uuid', read_only=True)
    confirmed_by_name = serializers.CharField(source='confirmed_by.name', read_only=True, allow_null=True)
    proof_image = serializers.SerializerMethodField()

    class Meta:
        model  = PaymentTransaction
        fields = [
            'id', 'order_uuid', 'user_name', 'user_email',
            'channel', 'amount', 'currency', 'status',
            'reference', 'proof_image', 'external_id',
            'admin_notes', 'confirmed_by_name',
            'created_at', 'paid_at', 'updated_at',
        ]

    def get_proof_image(self, obj):
        if not obj.proof_image:
            return None
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(obj.proof_image.url)
        return obj.proof_image.url


# ── Input serializers ──────────────────────────────────────────────────────────

class InitiatePaymentSerializer(serializers.Serializer):
    order_uuid = serializers.UUIDField()
    channel    = serializers.ChoiceField(choices=[
        PaymentMethod.CHANNEL_BANK,
        PaymentMethod.CHANNEL_STRIPE,
        PaymentMethod.CHANNEL_SELCOM,
    ])


class BankTransferSubmitSerializer(serializers.Serializer):
    transaction_id = serializers.IntegerField()
    reference      = serializers.CharField(max_length=255)
    proof_image    = serializers.ImageField(required=False, allow_null=True)


class ConfirmTransactionSerializer(serializers.Serializer):
    admin_notes = serializers.CharField(required=False, allow_blank=True, default='')
