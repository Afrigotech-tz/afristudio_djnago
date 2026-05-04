"""
artworks/views.py
Equivalent to Laravel's ArtworkController + CategoryController.
UUID-based lookup mirrors Laravel's route model binding on uuid.
"""

from django.db.models import Count
from django.shortcuts import get_object_or_404
from rest_framework import generics, status, serializers as drf_serializers, filters
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import IsAuthenticatedOrReadOnly, IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
    OpenApiParameter,
    OpenApiExample,
    OpenApiResponse,
    inline_serializer,
)
from drf_spectacular.types import OpenApiTypes

from apps.activity_logs.utils import log_activity
from .models import Category, Artwork, ArtworkImage
from .serializers import (
    CategorySerializer,
    StoreCategorySerializer,
    ArtworkSerializer,
    ArtworkImageSerializer,
    StoreArtworkSerializer,
    UpdateArtworkSerializer,
)

_NoContentSchema = inline_serializer('NoContent', fields={})


# ──────────────────────────────────────────────────────────
# Category Views  (replaces CategoryController)
# ──────────────────────────────────────────────────────────

@extend_schema_view(
    get=extend_schema(
        tags=['Categories'],
        summary='List all categories',
        description='Returns all artwork categories ordered alphabetically, each annotated with an `artworks_count`.',
        responses={200: CategorySerializer(many=True)},
    ),
    post=extend_schema(
        tags=['Categories'],
        summary='Create a new category',
        description='Creates a category and auto-generates a URL slug from the name. **Requires authentication.**',
        request=StoreCategorySerializer,
        responses={
            201: OpenApiResponse(response=CategorySerializer, description='Category created.'),
            400: OpenApiResponse(description='Name already exists or validation error.'),
            401: OpenApiResponse(description='Authentication required.'),
        },
        examples=[
            OpenApiExample(
                'Create category',
                request_only=True,
                value={'name': 'Oil Paintings'},
            ),
        ],
    ),
)
class CategoryListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/categories/        → list (public)
    POST /api/categories/        → create (auth required)
    """
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        return Category.objects.annotate(artworks_count=Count('artworks')).order_by('name')

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return StoreCategorySerializer
        return CategorySerializer

    def perform_create(self, serializer):
        category = serializer.save()
        log_activity(
            user=self.request.user,
            subject=category,
            description=f'Created new category: {category.name}',
            log_name='categories',
            event='created',
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        category = Category.objects.annotate(artworks_count=Count('artworks')).get(
            name=serializer.validated_data['name']
        )
        return Response(CategorySerializer(category).data, status=status.HTTP_201_CREATED)


@extend_schema_view(
    get=extend_schema(
        tags=['Categories'],
        summary='Retrieve a category',
        description='Returns a single category by its UUID.',
        responses={
            200: OpenApiResponse(response=CategorySerializer, description='Category details.'),
            404: OpenApiResponse(description='Category not found.'),
        },
    ),
    put=extend_schema(
        tags=['Categories'],
        summary='Update a category',
        description='Replaces the category name. **Requires authentication.**',
        request=StoreCategorySerializer,
        responses={
            200: OpenApiResponse(response=CategorySerializer, description='Category updated.'),
            400: OpenApiResponse(description='Validation error.'),
            401: OpenApiResponse(description='Authentication required.'),
            404: OpenApiResponse(description='Category not found.'),
        },
        examples=[
            OpenApiExample('Update', request_only=True, value={'name': 'Watercolours'}),
        ],
    ),
    patch=extend_schema(
        tags=['Categories'],
        summary='Partially update a category',
        request=StoreCategorySerializer,
        responses={
            200: OpenApiResponse(response=CategorySerializer, description='Category updated.'),
            401: OpenApiResponse(description='Authentication required.'),
        },
    ),
    destroy=extend_schema(
        tags=['Categories'],
        summary='Delete a category',
        description='Permanently deletes the category. **Requires authentication.**',
        responses={
            204: OpenApiResponse(description='Deleted — no content returned.'),
            401: OpenApiResponse(description='Authentication required.'),
            404: OpenApiResponse(description='Category not found.'),
        },
    ),
)
class CategoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET    /api/categories/<uuid>/  → show (public)
    PUT    /api/categories/<uuid>/  → update (auth required)
    DELETE /api/categories/<uuid>/  → destroy (auth required)
    """
    queryset = Category.objects.all()
    lookup_field = 'uuid'

    def get_permissions(self):
        if self.request.method == 'GET':
            return [IsAuthenticatedOrReadOnly()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        if self.request.method in ('PUT', 'PATCH'):
            return StoreCategorySerializer
        return CategorySerializer

    def perform_update(self, serializer):
        old_name = self.get_object().name
        category = serializer.save()
        log_activity(
            user=self.request.user,
            subject=category,
            description=f'Updated category from {old_name} to {category.name}',
            log_name='categories',
            event='updated',
        )

    def perform_destroy(self, instance):
        name = instance.name
        log_activity(
            user=self.request.user,
            subject=instance,
            description=f'Deleted category: {name}',
            log_name='categories',
            event='deleted',
        )
        instance.delete()

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ──────────────────────────────────────────────────────────
# Artwork Views  (replaces ArtworkController)
# ──────────────────────────────────────────────────────────

@extend_schema_view(
    get=extend_schema(
        tags=['Artworks'],
        summary='List artworks',
        description=(
            'Returns a paginated list of artworks. Pricing is converted to the requested currency '
            'via the `currency` query parameter (default: USD).'
        ),
        parameters=[
            OpenApiParameter(
                name='category_uuid',
                type=OpenApiTypes.UUID,
                location=OpenApiParameter.QUERY,
                description='Filter by category UUID.',
                required=False,
            ),
            OpenApiParameter(
                name='is_sold',
                type=OpenApiTypes.BOOL,
                location=OpenApiParameter.QUERY,
                description='Filter by sold status (`true` or `false`).',
                required=False,
            ),
            OpenApiParameter(
                name='currency',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Currency code for price conversion (e.g. `TZS`, `EUR`). Default: `USD`.',
                required=False,
                examples=[
                    OpenApiExample('USD (default)', value='USD'),
                    OpenApiExample('TZS', value='TZS'),
                ],
            ),
        ],
        responses={200: ArtworkSerializer(many=True)},
    ),
    post=extend_schema(
        tags=['Artworks'],
        summary='Upload a new artwork',
        description=(
            'Creates a new artwork listing. Send `multipart/form-data` when including an image. '
            '**Requires authentication.**'
        ),
        request=StoreArtworkSerializer,
        responses={
            201: OpenApiResponse(response=ArtworkSerializer, description='Artwork created.'),
            400: OpenApiResponse(description='Validation error (invalid category UUID, missing fields, etc.).'),
            401: OpenApiResponse(description='Authentication required.'),
        },
        examples=[
            OpenApiExample(
                'Create artwork',
                request_only=True,
                value={
                    'category_uuid': 'a1b2c3d4-0000-0000-0000-000000000001',
                    'name': 'Serengeti Sunrise',
                    'dimensions': '60x90',
                    'base_price': '250.00',
                    'is_sold': False,
                },
            ),
        ],
    ),
)
class ArtworkListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/artworks/   → list (public)
    POST /api/artworks/   → create (auth required)
    """
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'category__name', 'dimensions']
    ordering_fields = ['name', 'base_price', 'created_at']
    ordering = ['-created_at']

    def get_queryset(self):
        qs = Artwork.objects.select_related('category').prefetch_related('images')

        category_uuid = self.request.query_params.get('category_uuid')
        is_sold = self.request.query_params.get('is_sold')

        if category_uuid:
            qs = qs.filter(category__uuid=category_uuid)

        if is_sold is not None:
            qs = qs.filter(is_sold=is_sold.lower() in ('true', '1', 'yes'))

        return qs

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return StoreArtworkSerializer
        return ArtworkSerializer

    def get_serializer_context(self):
        return {'request': self.request}

    def perform_create(self, serializer):
        artwork = serializer.save()
        log_activity(
            user=self.request.user,
            subject=artwork,
            description=f'Created new artwork: {artwork.name}',
            log_name='artworks',
            event='created',
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        artwork = (
            Artwork.objects
            .select_related('category')
            .prefetch_related('images')
            .get(pk=serializer.instance.pk)
        )
        return Response(
            ArtworkSerializer(artwork, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema_view(
    get=extend_schema(
        tags=['Artworks'],
        summary='Retrieve an artwork',
        description='Returns full details of a single artwork by its UUID. Pricing converts to the `currency` query param.',
        parameters=[
            OpenApiParameter(
                name='currency',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Currency code for price conversion (default: `USD`).',
                required=False,
            ),
        ],
        responses={
            200: OpenApiResponse(response=ArtworkSerializer, description='Artwork details.'),
            404: OpenApiResponse(description='Artwork not found.'),
        },
    ),
    put=extend_schema(
        tags=['Artworks'],
        summary='Update an artwork',
        description='Replaces artwork fields. Send `multipart/form-data` to update the image. **Requires authentication.**',
        request=UpdateArtworkSerializer,
        responses={
            200: OpenApiResponse(response=ArtworkSerializer, description='Artwork updated.'),
            401: OpenApiResponse(description='Authentication required.'),
            404: OpenApiResponse(description='Artwork not found.'),
        },
        examples=[
            OpenApiExample(
                'Update artwork',
                request_only=True,
                value={'name': 'Serengeti Dusk', 'base_price': '300.00', 'is_sold': True},
            ),
        ],
    ),
    patch=extend_schema(
        tags=['Artworks'],
        summary='Partially update an artwork',
        request=UpdateArtworkSerializer,
        responses={
            200: OpenApiResponse(response=ArtworkSerializer, description='Artwork updated.'),
            401: OpenApiResponse(description='Authentication required.'),
        },
    ),
    destroy=extend_schema(
        tags=['Artworks'],
        summary='Delete an artwork',
        description='Permanently deletes the artwork and its image file. **Requires authentication.**',
        responses={
            204: OpenApiResponse(description='Deleted — no content returned.'),
            401: OpenApiResponse(description='Authentication required.'),
            404: OpenApiResponse(description='Artwork not found.'),
        },
    ),
)
class ArtworkDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET    /api/artworks/<uuid>/   → show (public)
    PUT    /api/artworks/<uuid>/   → update (auth required)
    DELETE /api/artworks/<uuid>/   → destroy (auth required)
    """
    queryset = Artwork.objects.select_related('category').prefetch_related('images')
    lookup_field = 'uuid'
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_permissions(self):
        if self.request.method == 'GET':
            return [IsAuthenticatedOrReadOnly()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        if self.request.method in ('PUT', 'PATCH'):
            return UpdateArtworkSerializer
        return ArtworkSerializer

    def get_serializer_context(self):
        return {'request': self.request}

    def perform_update(self, serializer):
        old_name = self.get_object().name
        artwork = serializer.save()
        log_activity(
            user=self.request.user,
            subject=artwork,
            description=f'Updated artwork from {old_name} to {artwork.name}',
            log_name='artworks',
            event='updated',
        )

    def perform_destroy(self, instance):
        name = instance.name
        if instance.image:
            instance.image.delete(save=False)
        log_activity(
            user=self.request.user,
            subject=instance,
            description=f'Deleted artwork: {name}',
            log_name='artworks',
            event='deleted',
        )
        instance.delete()

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ──────────────────────────────────────────────────────────
# Artwork Image Views
# ──────────────────────────────────────────────────────────

class ArtworkImageListCreateView(generics.GenericAPIView):
    """
    GET  /api/artworks/<uuid>/images/  → list images (public)
    POST /api/artworks/<uuid>/images/  → upload image (auth required)
    """
    parser_classes = [MultiPartParser, FormParser]

    def _get_artwork(self, uuid):
        return get_object_or_404(Artwork, uuid=uuid)

    def get(self, request, uuid):
        artwork = self._get_artwork(uuid)
        images = artwork.images.all()
        serializer = ArtworkImageSerializer(images, many=True, context={'request': request})
        return Response(serializer.data)

    def post(self, request, uuid):
        if not request.user.is_authenticated:
            return Response({'detail': 'Authentication required.'}, status=status.HTTP_401_UNAUTHORIZED)

        artwork = self._get_artwork(uuid)
        image_file = request.FILES.get('image')
        if not image_file:
            return Response({'image': 'This field is required.'}, status=status.HTTP_400_BAD_REQUEST)

        is_primary_str = request.data.get('is_primary', 'false')
        is_primary = is_primary_str.lower() in ('true', '1') if isinstance(is_primary_str, str) else bool(is_primary_str)
        description = request.data.get('description', '')

        # Auto-set as primary if it's the first image
        if not artwork.images.exists():
            is_primary = True

        order = artwork.images.count()
        img = ArtworkImage.objects.create(
            artwork=artwork,
            image=image_file,
            description=description,
            is_primary=is_primary,
            order=order,
        )
        return Response(
            ArtworkImageSerializer(img, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )


class ArtworkImageDetailView(generics.GenericAPIView):
    """
    DELETE /api/artworks/<uuid>/images/<pk>/              → delete image
    PATCH  /api/artworks/<uuid>/images/<pk>/set-primary/  → set as primary
    """
    permission_classes = [IsAuthenticated]

    def _get_image(self, uuid, pk):
        return get_object_or_404(ArtworkImage, pk=pk, artwork__uuid=uuid)

    def delete(self, request, uuid, pk):
        img = self._get_image(uuid, pk)
        was_primary = img.is_primary
        img.image.delete(save=False)
        img.delete()

        if was_primary:
            next_img = ArtworkImage.objects.filter(artwork__uuid=uuid).first()
            if next_img:
                next_img.is_primary = True
                next_img.save(update_fields=['is_primary'])

        return Response(status=status.HTTP_204_NO_CONTENT)

    def patch(self, request, uuid, pk):
        img = self._get_image(uuid, pk)
        if request.path.endswith('/set-primary/'):
            img.is_primary = True
            img.save(update_fields=['is_primary'])
        else:
            fields = []
            if 'description' in request.data:
                img.description = request.data.get('description', '')
                fields.append('description')
            if 'order' in request.data:
                img.order = request.data.get('order') or 0
                fields.append('order')
            if 'is_primary' in request.data:
                is_primary = request.data.get('is_primary')
                img.is_primary = is_primary.lower() in ('true', '1') if isinstance(is_primary, str) else bool(is_primary)
                fields.append('is_primary')
            if fields:
                img.save(update_fields=fields)
        return Response(
            ArtworkImageSerializer(img, context={'request': request}).data
        )
