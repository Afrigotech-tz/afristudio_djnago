"""
cart/views.py

GET    /api/cart/                  — view cart
POST   /api/cart/items/            — add artwork to cart (blocked if in live auction)
DELETE /api/cart/items/<uuid>/     — remove item from cart
"""

from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from drf_spectacular.utils import extend_schema

from .models import Cart, CartItem
from .serializers import CartSerializer, AddToCartSerializer, CartItemSerializer


class CartView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Cart'], summary='Get current user cart', responses={200: CartSerializer})
    def get(self, request):
        cart, _ = Cart.objects.get_or_create(user=request.user)
        return Response(CartSerializer(cart, context={'request': request}).data)


class CartItemAddView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Cart'], summary='Add artwork to cart', request=AddToCartSerializer, responses={201: CartItemSerializer})
    def post(self, request):
        serializer = AddToCartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        from apps.artworks.models import Artwork
        from apps.auctions.models import Auction

        artwork = get_object_or_404(Artwork, uuid=serializer.validated_data['artwork_uuid'])

        if artwork.is_sold:
            return Response({'message': 'This artwork has already been sold.'}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        # Block if artwork is in a live auction
        if hasattr(artwork, 'auction') and artwork.auction.status == Auction.STATUS_LIVE:
            return Response(
                {'message': 'This artwork is currently in a live auction and cannot be added to cart.'},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        cart, _ = Cart.objects.get_or_create(user=request.user)

        if CartItem.objects.filter(cart=cart, artwork=artwork).exists():
            return Response({'message': 'This artwork is already in your cart.'}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        item = CartItem.objects.create(
            cart=cart,
            artwork=artwork,
            source=CartItem.SOURCE_MANUAL,
            price=artwork.base_price,
            currency=artwork.base_currency,
        )
        return Response(CartItemSerializer(item, context={'request': request}).data, status=status.HTTP_201_CREATED)


class CartItemRemoveView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Cart'], summary='Remove item from cart')
    def delete(self, request, uuid):
        cart = get_object_or_404(Cart, user=request.user)
        item = get_object_or_404(CartItem, uuid=uuid, cart=cart)

        # Auction-won items cannot be manually removed
        if item.source == CartItem.SOURCE_AUCTION_WIN:
            return Response({'message': 'Auction-won items cannot be removed from cart.'}, status=status.HTTP_403_FORBIDDEN)

        item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
