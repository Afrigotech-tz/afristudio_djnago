"""
payments/views.py

GET  /api/payments/methods/                   — active methods (authenticated)
GET  /api/payments/methods/admin/             — all methods with full config (admin)
PATCH /api/payments/methods/<channel>/        — configure a channel (admin)

POST /api/payments/initiate/                  — create a PaymentTransaction for an Order
POST /api/payments/bank-transfer/submit/      — user submits reference + optional proof
POST /api/payments/stripe/webhook/            — Stripe webhook (no auth)
POST /api/payments/selcom/callback/           — Selcom callback (no auth)

GET  /api/payments/transactions/              — list all transactions (admin)
GET  /api/payments/transactions/<id>/         — single transaction detail (admin/owner)
POST /api/payments/transactions/<id>/confirm/ — manually mark completed (admin)
POST /api/payments/transactions/<id>/cancel/  — cancel a transaction (admin)
"""

from django.utils import timezone
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from .models import PaymentMethod, PaymentTransaction
from .serializers import (
    PaymentMethodPublicSerializer, PaymentMethodAdminSerializer,
    PaymentTransactionSerializer,
    InitiatePaymentSerializer, BankTransferSubmitSerializer,
    ConfirmTransactionSerializer,
)
from apps.orders.models import Order
from apps.activity_logs.utils import log_activity
from apps.notifications.tasks import notify_async


def _update_order_payment_channel(order: Order, channel: str):
    order.payment_channel = channel
    order.save(update_fields=['payment_channel', 'updated_at'])


# ── Payment Methods (public / admin) ──────────────────────────────────────────

class ActivePaymentMethodsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        methods = PaymentMethod.objects.filter(is_active=True).order_by('sort_order')
        return Response(PaymentMethodPublicSerializer(methods, many=True).data)


class AdminPaymentMethodsView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        methods = PaymentMethod.objects.all().order_by('sort_order')
        return Response(PaymentMethodAdminSerializer(methods, many=True).data)


class AdminPaymentMethodDetailView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request, channel):
        method = get_object_or_404(PaymentMethod, channel=channel)
        return Response(PaymentMethodAdminSerializer(method).data)

    def patch(self, request, channel):
        method = get_object_or_404(PaymentMethod, channel=channel)
        serializer = PaymentMethodAdminSerializer(method, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        log_activity(
            user=request.user, subject=None,
            description=f'Updated payment method "{method.display_name}"',
            log_name='payments', event='payment_method_updated',
        )
        return Response(PaymentMethodAdminSerializer(method).data)


# ── Initiate Payment ──────────────────────────────────────────────────────────

class InitiatePaymentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = InitiatePaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        order = get_object_or_404(Order, uuid=data['order_uuid'], user=request.user)

        # Block if order already has a completed/processing transaction
        existing = order.transactions.filter(
            status__in=[PaymentTransaction.STATUS_COMPLETED, PaymentTransaction.STATUS_PROCESSING]
        ).first()
        if existing:
            return Response(
                {'message': 'This order already has an active or completed payment.'},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        channel = data['channel']
        method  = get_object_or_404(PaymentMethod, channel=channel, is_active=True)

        # Cancel any previous pending transactions for this order
        order.transactions.filter(status=PaymentTransaction.STATUS_PENDING).update(
            status=PaymentTransaction.STATUS_CANCELLED
        )

        txn = PaymentTransaction.objects.create(
            order    = order,
            user     = request.user,
            channel  = channel,
            amount   = order.total,
            currency = order.currency,
        )

        # Update order's payment channel
        _update_order_payment_channel(order, channel)

        response_data = {'transaction_id': txn.id, 'channel': channel, 'amount': str(txn.amount), 'currency': txn.currency}

        if channel == PaymentMethod.CHANNEL_BANK:
            cfg = method.config
            response_data['bank_details'] = {
                'bank_name':      cfg.get('bank_name', ''),
                'account_number': cfg.get('account_number', ''),
                'account_name':   cfg.get('account_name', ''),
                'branch':         cfg.get('branch', ''),
                'swift_code':     cfg.get('swift_code', ''),
                'instructions':   cfg.get('instructions', ''),
            }

        elif channel == PaymentMethod.CHANNEL_STRIPE:
            try:
                import stripe
                stripe.api_key = method.config.get('secret_key', '')
                intent = stripe.PaymentIntent.create(
                    amount   = int(txn.amount * 100),
                    currency = txn.currency.lower(),
                    metadata = {'transaction_id': txn.id, 'order_uuid': str(order.uuid)},
                )
                txn.external_id      = intent['id']
                txn.status           = PaymentTransaction.STATUS_PROCESSING
                txn.gateway_response = {'client_secret': intent['client_secret']}
                txn.save(update_fields=['external_id', 'status', 'gateway_response', 'updated_at'])
                response_data['client_secret']   = intent['client_secret']
                response_data['publishable_key'] = method.config.get('publishable_key', '')
            except Exception as e:
                txn.status = PaymentTransaction.STATUS_FAILED
                txn.gateway_response = {'error': str(e)}
                txn.save(update_fields=['status', 'gateway_response', 'updated_at'])
                return Response({'message': f'Stripe error: {e}'}, status=status.HTTP_502_BAD_GATEWAY)

        elif channel == PaymentMethod.CHANNEL_SELCOM:
            try:
                import requests as req, hashlib, base64
                cfg    = method.config
                vendor = cfg.get('vendor_id', '')
                vpass  = cfg.get('vendor_pass', '')
                api_url = cfg.get('api_url', 'https://apigwtest.selcommobile.com/v1')
                token  = base64.b64encode(f'{vendor}:{vpass}'.encode()).decode()
                payload = {
                    'vendor':           vendor,
                    'order_id':         str(txn.id),
                    'buyer_email':      request.user.email,
                    'buyer_name':       request.user.name,
                    'buyer_phone':      getattr(request.user, 'phone', '') or '',
                    'amount':           float(txn.amount),
                    'currency':         txn.currency,
                    'redirect_url':     cfg.get('redirect_url', ''),
                    'cancel_url':       cfg.get('cancel_url', ''),
                    'webhook':          cfg.get('callback_url', ''),
                    'no_of_items':      order.items.count(),
                }
                headers = {
                    'Authorization': f'Basic {token}',
                    'Content-Type':  'application/json',
                }
                resp = req.post(f'{api_url}/checkout/create-order', json=payload, headers=headers, timeout=15)
                resp_data = resp.json()
                if resp.status_code == 200 and resp_data.get('result') == '000':
                    txn.external_id      = resp_data.get('transid', '')
                    txn.status           = PaymentTransaction.STATUS_PROCESSING
                    txn.gateway_response = resp_data
                    txn.save(update_fields=['external_id', 'status', 'gateway_response', 'updated_at'])
                    response_data['payment_url'] = resp_data.get('payment_gateway_url', '')
                else:
                    txn.status = PaymentTransaction.STATUS_FAILED
                    txn.gateway_response = resp_data
                    txn.save(update_fields=['status', 'gateway_response', 'updated_at'])
                    return Response({'message': resp_data.get('message', 'Selcom error')}, status=status.HTTP_502_BAD_GATEWAY)
            except Exception as e:
                txn.status = PaymentTransaction.STATUS_FAILED
                txn.gateway_response = {'error': str(e)}
                txn.save(update_fields=['status', 'gateway_response', 'updated_at'])
                return Response({'message': f'Selcom error: {e}'}, status=status.HTTP_502_BAD_GATEWAY)

        return Response(response_data, status=status.HTTP_201_CREATED)


# ── Bank Transfer: submit reference ───────────────────────────────────────────

class BankTransferSubmitView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes     = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        serializer = BankTransferSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        txn = get_object_or_404(
            PaymentTransaction,
            id=data['transaction_id'],
            user=request.user,
            channel=PaymentMethod.CHANNEL_BANK,
        )

        if txn.status not in (PaymentTransaction.STATUS_PENDING, PaymentTransaction.STATUS_FAILED):
            return Response(
                {'message': 'This transaction cannot be updated.'},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        txn.reference   = data['reference']
        txn.status      = PaymentTransaction.STATUS_PROCESSING
        if 'proof_image' in request.FILES:
            txn.proof_image = request.FILES['proof_image']
        txn.save(update_fields=['reference', 'status', 'proof_image', 'updated_at'])

        # Notify admins
        notify_async(
            user_id=None,
            to_email=None,   # notify superusers — handled via activity log / admin panel
            subject=f'Bank Transfer Reference Submitted — Order #{txn.order_id}',
            message=(
                f'{request.user.name} submitted a bank transfer reference '
                f'"{data["reference"]}" for Order #{txn.order_id} '
                f'({txn.amount} {txn.currency}). Please verify and confirm.'
            ),
        )
        log_activity(
            user=request.user, subject=txn.order,
            description=f'Submitted bank transfer reference "{data["reference"]}" for Order #{txn.order_id}',
            log_name='payments', event='bank_transfer_submitted',
        )
        return Response(PaymentTransactionSerializer(txn, context={'request': request}).data)


# ── Stripe Webhook ────────────────────────────────────────────────────────────

class StripeWebhookView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        try:
            import stripe
            method = PaymentMethod.objects.filter(channel=PaymentMethod.CHANNEL_STRIPE).first()
            if not method:
                return Response(status=status.HTTP_200_OK)

            webhook_secret = method.config.get('webhook_secret', '')
            sig_header     = request.META.get('HTTP_STRIPE_SIGNATURE', '')
            event = stripe.Webhook.construct_event(request.body, sig_header, webhook_secret)

            if event['type'] == 'payment_intent.succeeded':
                intent = event['data']['object']
                txn_id = intent.get('metadata', {}).get('transaction_id')
                if txn_id:
                    _complete_transaction(txn_id, intent['id'])

            elif event['type'] == 'payment_intent.payment_failed':
                intent = event['data']['object']
                txn_id = intent.get('metadata', {}).get('transaction_id')
                if txn_id:
                    PaymentTransaction.objects.filter(id=txn_id).update(
                        status=PaymentTransaction.STATUS_FAILED,
                        gateway_response=intent,
                        updated_at=timezone.now(),
                    )
        except Exception:
            pass
        return Response(status=status.HTTP_200_OK)


# ── Selcom Callback ───────────────────────────────────────────────────────────

class SelcomCallbackView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        data    = request.data
        order_id = data.get('order_id') or data.get('reference')
        result   = data.get('result') or data.get('transactionstatus', '')

        if order_id and result in ('000', 'success', 'COMPLETED'):
            _complete_transaction(order_id, data.get('transid', ''))
        return Response({'result': '000', 'message': 'Callback received'})


def _complete_transaction(txn_id, external_id=''):
    try:
        txn = PaymentTransaction.objects.select_related('order', 'user').get(id=txn_id)
    except PaymentTransaction.DoesNotExist:
        return

    txn.status      = PaymentTransaction.STATUS_COMPLETED
    txn.paid_at     = timezone.now()
    txn.external_id = external_id or txn.external_id
    txn.save(update_fields=['status', 'paid_at', 'external_id', 'updated_at'])

    # Confirm the order
    order = txn.order
    if order.status == Order.STATUS_PENDING:
        order.status = Order.STATUS_CONFIRMED
        order.save(update_fields=['status', 'updated_at'])

    notify_async(
        user_id=txn.user_id,
        subject=f'Payment Confirmed — Order #{order.id}',
        message=(
            f'Hi {txn.user.name}, your payment of {txn.amount} {txn.currency} '
            f'for Order #{order.id} has been confirmed. '
            f'Your order is now being processed.'
        ),
        template='emails/payment_confirmed.html',
        context={
            'name':       txn.user.name,
            'order_id':   order.id,
            'amount':     str(txn.amount),
            'currency':   txn.currency,
            'channel':    txn.channel.replace('_', ' ').title(),
        },
    )


# ── Transactions (admin) ──────────────────────────────────────────────────────

class TransactionListView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        qs = PaymentTransaction.objects.select_related('order', 'user', 'confirmed_by').all()
        channel = request.query_params.get('channel')
        txn_status = request.query_params.get('status')
        if channel:
            qs = qs.filter(channel=channel)
        if txn_status:
            qs = qs.filter(status=txn_status)
        return Response(PaymentTransactionSerializer(qs, many=True, context={'request': request}).data)


class TransactionDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        txn = get_object_or_404(PaymentTransaction, pk=pk)
        if not (request.user.is_staff or request.user.is_superuser or txn.user == request.user):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied()
        return Response(PaymentTransactionSerializer(txn, context={'request': request}).data)


class ConfirmTransactionView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        txn = get_object_or_404(PaymentTransaction, pk=pk)
        if txn.status == PaymentTransaction.STATUS_COMPLETED:
            return Response({'message': 'Transaction already completed.'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = ConfirmTransactionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        txn.status       = PaymentTransaction.STATUS_COMPLETED
        txn.paid_at      = timezone.now()
        txn.confirmed_by = request.user
        txn.admin_notes  = serializer.validated_data.get('admin_notes', '')
        txn.save(update_fields=['status', 'paid_at', 'confirmed_by', 'admin_notes', 'updated_at'])

        # Confirm the order
        order = txn.order
        if order.status == Order.STATUS_PENDING:
            order.status = Order.STATUS_CONFIRMED
            order.save(update_fields=['status', 'updated_at'])

        _complete_transaction(txn.id, txn.external_id)
        log_activity(
            user=request.user, subject=order,
            description=f'Manually confirmed payment for Order #{order.id} via {txn.channel}',
            log_name='payments', event='payment_confirmed',
        )
        return Response(PaymentTransactionSerializer(txn, context={'request': request}).data)


class CancelTransactionView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        txn = get_object_or_404(PaymentTransaction, pk=pk)
        if txn.status in (PaymentTransaction.STATUS_COMPLETED, PaymentTransaction.STATUS_CANCELLED):
            return Response({'message': 'Cannot cancel this transaction.'}, status=status.HTTP_400_BAD_REQUEST)
        txn.status = PaymentTransaction.STATUS_CANCELLED
        txn.save(update_fields=['status', 'updated_at'])
        return Response(PaymentTransactionSerializer(txn, context={'request': request}).data)
