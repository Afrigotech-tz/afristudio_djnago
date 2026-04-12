"""
orders/views.py

POST /api/orders/checkout/        — checkout cart → create order
GET  /api/orders/                 — list user's orders
GET  /api/orders/<uuid>/          — order detail
PUT  /api/orders/<uuid>/status/   — update status (admin)
"""

from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework import status
from drf_spectacular.utils import extend_schema

from .models import Order, OrderItem
from .serializers import OrderSerializer, CheckoutSerializer, UpdateOrderStatusSerializer
from apps.cart.models import Cart, CartItem
from apps.activity_logs.utils import log_activity
from apps.notifications.service import notify


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

            # Clear cart after checkout
            items.delete()

        notify(
            user=request.user,
            subject='Your Afristudio order has been placed',
            message=f'Hi {request.user.name}, your order #{order.id} has been placed successfully. Total: {order.total} {order.currency}.',
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

    @extend_schema(tags=['Orders'], summary='List my orders', responses={200: OrderSerializer(many=True)})
    def get(self, request):
        orders = Order.objects.filter(user=request.user).prefetch_related('items')
        return Response(OrderSerializer(orders, many=True).data)


class OrderDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Orders'], summary='Get order detail', responses={200: OrderSerializer})
    def get(self, request, uuid):
        order = get_object_or_404(Order, uuid=uuid, user=request.user)
        return Response(OrderSerializer(order).data)


class OrderStatusUpdateView(APIView):
    permission_classes = [IsAdminUser]

    @extend_schema(
        tags=['Orders'],
        summary='Update order status (admin only)',
        request=UpdateOrderStatusSerializer,
        responses={200: OrderSerializer},
    )
    def put(self, request, uuid):
        order = get_object_or_404(Order, uuid=uuid)
        serializer = UpdateOrderStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        old_status = order.status
        order.status = serializer.validated_data['status']
        order.save(update_fields=['status', 'updated_at'])

        # Notify user of status change
        notify(
            user=order.user,
            subject=f'Your order status has been updated to {order.get_status_display()}',
            message=f'Hi {order.user.name}, your order #{order.id} status changed from {old_status} to {order.status}.',
        )

        log_activity(
            user=request.user,
            subject=order,
            description=f'Order #{order.id} status changed: {old_status} → {order.status}',
            log_name='orders',
            event='order_status_updated',
        )

        return Response(OrderSerializer(order).data)
