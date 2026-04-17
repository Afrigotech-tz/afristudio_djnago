"""
orders/views.py

POST /api/orders/checkout/        — checkout cart → create order
GET  /api/orders/                 — own orders (all orders if admin/staff)
GET  /api/orders/<uuid>/          — order detail (any order if admin/staff)
PUT  /api/orders/<uuid>/status/   — update status (admin/staff only)

Access rules:
  • Regular users  → see and act on their own orders only.
  • Staff / admins → see ALL orders; can filter by status, user email, user uuid.
"""

from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from drf_spectacular.utils import extend_schema, OpenApiParameter

from .models import Order, OrderItem
from .serializers import OrderSerializer, CheckoutSerializer, UpdateOrderStatusSerializer
from apps.cart.models import Cart, CartItem
from apps.activity_logs.utils import log_activity
from apps.notifications.tasks import notify_async
from apps.accounts.permissions import IsAdminOrStaff


def _is_manager(user) -> bool:
    """True for staff, superusers, or any user with explicit order management permission."""
    return user.is_staff or user.is_superuser or user.has_perm('orders.change_order')


class CheckoutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['Orders'],
        summary='Checkout — convert cart to order',
        request=CheckoutSerializer,
        responses={201: OrderSerializer},
    )
    def post(self, request):
        serializer = CheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        cart = get_object_or_404(Cart, user=request.user)
        items = cart.items.select_related('artwork', 'auction').all()

        if not items.exists():
            return Response({'message': 'Your cart is empty.'}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        total = sum(item.price for item in items)

        with transaction.atomic():
            order = Order.objects.create(
                user=request.user,
                total=total,
                currency=items.first().currency,
                delivery_name=data['delivery_name'],
                delivery_phone=data['delivery_phone'],
                delivery_address=data['delivery_address'],
                delivery_city=data['delivery_city'],
                delivery_country=data['delivery_country'],
                notes=data.get('notes', ''),
            )

            for item in items:
                OrderItem.objects.create(
                    order=order,
                    artwork=item.artwork,
                    artwork_name=item.artwork.name,
                    price=item.price,
                    currency=item.currency,
                    auction=item.auction,
                )

            items.delete()

        notify_async(
            user_id=request.user.pk,
            subject='Your Afristudio order has been placed',
            message=(
                f'Hi {request.user.name}, your order #{order.id} has been placed. '
                f'Total: {order.total} {order.currency}.'
            ),
            template='emails/order_placed.html',
            context={
                'name': request.user.name,
                'order_id': order.id,
                'total': str(order.total),
                'currency': order.currency,
                'delivery_city': order.delivery_city,
            },
        )
        log_activity(
            user=request.user,
            subject=order,
            description=f'Placed order #{order.id} — {order.total} {order.currency}',
            log_name='orders',
            event='order_placed',
        )
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)


class OrderListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['Orders'],
        summary='List orders',
        description=(
            'Returns the authenticated user\'s own orders. '
            'Staff and admins receive **all** orders and can filter by `status`, '
            '`user_email`, or `user_uuid`.'
        ),
        parameters=[
            OpenApiParameter('status',     str, description='Filter by order status'),
            OpenApiParameter('user_email', str, description='Filter by buyer email (admin only)'),
            OpenApiParameter('user_uuid',  str, description='Filter by buyer UUID (admin only)'),
        ],
        responses={200: OrderSerializer(many=True)},
    )
    def get(self, request):
        if _is_manager(request.user):
            qs = Order.objects.select_related('user').prefetch_related('items').all()

            status_filter = request.query_params.get('status')
            if status_filter:
                qs = qs.filter(status=status_filter)

            user_email = request.query_params.get('user_email')
            if user_email:
                qs = qs.filter(user__email__icontains=user_email)

            user_uuid = request.query_params.get('user_uuid')
            if user_uuid:
                qs = qs.filter(user__uuid=user_uuid)
        else:
            qs = Order.objects.filter(user=request.user).prefetch_related('items')

        return Response(OrderSerializer(qs, many=True).data)


class OrderDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['Orders'],
        summary='Get order detail',
        description='Returns a single order. Staff/admins can view any order; regular users only their own.',
        responses={200: OrderSerializer},
    )
    def get(self, request, uuid):
        if _is_manager(request.user):
            order = get_object_or_404(Order.objects.prefetch_related('items'), uuid=uuid)
        else:
            order = get_object_or_404(Order.objects.prefetch_related('items'), uuid=uuid, user=request.user)
        return Response(OrderSerializer(order).data)


class OrderStatusUpdateView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOrStaff]

    @extend_schema(
        tags=['Orders'],
        summary='Update order status (staff/admin only)',
        request=UpdateOrderStatusSerializer,
        responses={200: OrderSerializer},
    )
    def put(self, request, uuid):
        order = get_object_or_404(Order.objects.select_related('user'), uuid=uuid)
        serializer = UpdateOrderStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        old_status = order.status
        new_status = serializer.validated_data['status']
        order.status = new_status
        order.save(update_fields=['status', 'updated_at'])

        notify_async(
            user_id=order.user.pk,
            subject=f'Order #{order.id} — status updated to {order.get_status_display()}',
            message=(
                f'Hi {order.user.name}, your order #{order.id} status has changed '
                f'from {old_status} to {new_status}.'
            ),
        )
        log_activity(
            user=request.user,
            subject=order,
            description=f'Order #{order.id} status: {old_status} → {new_status}',
            log_name='orders',
            event='order_status_updated',
        )
        return Response(OrderSerializer(order).data)
