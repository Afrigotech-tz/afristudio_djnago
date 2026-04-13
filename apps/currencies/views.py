"""
currencies/views.py
Equivalent to Laravel's CurrencyController.
Public: list + show. Auth required: create, update, delete.
"""

from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticatedOrReadOnly, IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
    OpenApiExample,
    OpenApiResponse,
)

from apps.activity_logs.utils import log_activity
from .models import Currency
from .serializers import CurrencySerializer, StoreCurrencySerializer


@extend_schema(
    tags=['Currencies'],
    summary='List all currencies (public)',
    description='Returns all configured currencies with their exchange rates. **No authentication required.**',
    responses={200: OpenApiResponse(response=CurrencySerializer(many=True), description='List of currencies.')},
)
class PublicCurrencyListView(generics.ListAPIView):
    """
    GET /api/currencies/public/  → list all currencies (no auth required)
    """
    queryset = Currency.objects.all()
    serializer_class = CurrencySerializer
    permission_classes = []


@extend_schema_view(
    get=extend_schema(
        tags=['Currencies'],
        summary='List all currencies',
        description='Returns all configured currencies with their exchange rates relative to USD. **Requires authentication.**',
        responses={
            200: OpenApiResponse(response=CurrencySerializer(many=True), description='List of currencies.'),
            401: OpenApiResponse(description='Authentication required.'),
        },
    ),
    post=extend_schema(
        tags=['Currencies'],
        summary='Create a new currency',
        description='Adds a new currency with its exchange rate. Currency codes are stored in uppercase. **Requires authentication.**',
        request=StoreCurrencySerializer,
        responses={
            201: OpenApiResponse(response=CurrencySerializer, description='Currency created.'),
            400: OpenApiResponse(description='Duplicate code or validation error.'),
            401: OpenApiResponse(description='Authentication required.'),
        },
        examples=[
            OpenApiExample(
                'Create currency',
                request_only=True,
                value={'code': 'ZAR', 'symbol': 'R', 'exchange_rate': '18.95000000'},
            ),
        ],
    ),
)
class CurrencyListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/currencies/   → list (auth required)
    POST /api/currencies/   → create (auth required)
    """
    queryset = Currency.objects.all()
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return StoreCurrencySerializer
        return CurrencySerializer

    def perform_create(self, serializer):
        currency = serializer.save()
        log_activity(
            user=self.request.user,
            subject=currency,
            description=f'Created new currency: {currency.code}',
            log_name='currencies',
            event='created',
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(
            CurrencySerializer(serializer.instance).data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema_view(
    get=extend_schema(
        tags=['Currencies'],
        summary='Retrieve a currency',
        description='Returns a single currency by its UUID. **Requires authentication.**',
        responses={
            200: OpenApiResponse(response=CurrencySerializer, description='Currency details.'),
            401: OpenApiResponse(description='Authentication required.'),
            404: OpenApiResponse(description='Currency not found.'),
        },
    ),
    put=extend_schema(
        tags=['Currencies'],
        summary='Update a currency',
        description='Replaces all currency fields. **Requires authentication.**',
        request=StoreCurrencySerializer,
        responses={
            200: OpenApiResponse(response=CurrencySerializer, description='Currency updated.'),
            400: OpenApiResponse(description='Validation error.'),
            401: OpenApiResponse(description='Authentication required.'),
            404: OpenApiResponse(description='Currency not found.'),
        },
        examples=[
            OpenApiExample(
                'Update currency',
                request_only=True,
                value={'code': 'TZS', 'symbol': 'TSh', 'exchange_rate': '2600.00000000'},
            ),
        ],
    ),
    patch=extend_schema(
        tags=['Currencies'],
        summary='Partially update a currency',
        request=StoreCurrencySerializer,
        responses={
            200: OpenApiResponse(response=CurrencySerializer, description='Currency updated.'),
            401: OpenApiResponse(description='Authentication required.'),
        },
        examples=[
            OpenApiExample(
                'Update rate only',
                request_only=True,
                value={'exchange_rate': '2620.50000000'},
            ),
        ],
    ),
    destroy=extend_schema(
        tags=['Currencies'],
        summary='Delete a currency',
        description='Permanently removes a currency. **Requires authentication.**',
        responses={
            204: OpenApiResponse(description='Deleted — no content returned.'),
            401: OpenApiResponse(description='Authentication required.'),
            404: OpenApiResponse(description='Currency not found.'),
        },
    ),
)
class CurrencyDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET    /api/currencies/<uuid>/   → show (auth required)
    PUT    /api/currencies/<uuid>/   → update (auth required)
    DELETE /api/currencies/<uuid>/   → destroy (auth required)
    """
    queryset = Currency.objects.all()
    lookup_field = 'uuid'
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method in ('PUT', 'PATCH'):
            return StoreCurrencySerializer
        return CurrencySerializer

    def perform_update(self, serializer):
        currency = serializer.save()
        log_activity(
            user=self.request.user,
            subject=currency,
            description=f'Updated currency: {currency.code}',
            log_name='currencies',
            event='updated',
        )

    def perform_destroy(self, instance):
        code = instance.code
        log_activity(
            user=self.request.user,
            subject=instance,
            description=f'Deleted currency: {code}',
            log_name='currencies',
            event='deleted',
        )
        instance.delete()

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)
