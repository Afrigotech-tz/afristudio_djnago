"""
site_config/views.py
Endpoints for landing hero image, contact info, and contact messages.
"""

from rest_framework import generics, status
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiResponse

from .models import LandingHero, HeroContent, ContactInfo, ContactMessage
from .serializers import (
    LandingHeroSerializer,
    LandingHeroUpdateSerializer,
    HeroContentSerializer,
    HeroContentUpdateSerializer,
    ContactInfoSerializer,
    ContactInfoUpdateSerializer,
    ContactMessageCreateSerializer,
    ContactMessageSerializer,
    ContactMessageStatusSerializer,
)


# ──────────────────────────────────────────────
# Landing Hero
# ──────────────────────────────────────────────

class LandingHeroView(APIView):
    """
    GET  /api/site/hero/   → public — returns current hero image URL
    PUT  /api/site/hero/   → admin  — replace the hero image
    """
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_permissions(self):
        if self.request.method == 'GET':
            return [AllowAny()]
        return [IsAdminUser()]

    @extend_schema(
        tags=['Site Config'],
        summary='Get landing hero image',
        responses={200: LandingHeroSerializer},
    )
    def get(self, request):
        hero = LandingHero.load()
        return Response(LandingHeroSerializer(hero, context={'request': request}).data)

    @extend_schema(
        tags=['Site Config'],
        summary='Update landing hero image',
        request=LandingHeroUpdateSerializer,
        responses={
            200: LandingHeroSerializer,
            400: OpenApiResponse(description='Validation error.'),
            403: OpenApiResponse(description='Admin access required.'),
        },
    )
    def put(self, request):
        hero = LandingHero.load()
        serializer = LandingHeroUpdateSerializer(hero, data=request.data)
        serializer.is_valid(raise_exception=True)
        # Remove old image file before saving new one
        if hero.image:
            hero.image.delete(save=False)
        serializer.save()
        hero.refresh_from_db()
        return Response(LandingHeroSerializer(hero, context={'request': request}).data)


# ──────────────────────────────────────────────
# Hero Text Content
# ──────────────────────────────────────────────

class HeroContentView(APIView):
    """
    GET   /api/site/hero-content/   → public — returns hero text fields
    PATCH /api/site/hero-content/   → admin  — update hero text
    """

    def get_permissions(self):
        if self.request.method == 'GET':
            return [AllowAny()]
        return [IsAdminUser()]

    @extend_schema(
        tags=['Site Config'],
        summary='Get landing hero text',
        responses={200: HeroContentSerializer},
    )
    def get(self, request):
        content = HeroContent.load()
        return Response(HeroContentSerializer(content).data)

    @extend_schema(
        tags=['Site Config'],
        summary='Update landing hero text',
        request=HeroContentUpdateSerializer,
        responses={200: HeroContentSerializer},
    )
    def patch(self, request):
        content = HeroContent.load()
        serializer = HeroContentUpdateSerializer(content, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        content.refresh_from_db()
        return Response(HeroContentSerializer(content).data)


# ──────────────────────────────────────────────
# Contact Information
# ──────────────────────────────────────────────

class ContactInfoView(APIView):
    """
    GET   /api/site/contact-info/   → public
    PATCH /api/site/contact-info/   → admin
    """

    def get_permissions(self):
        if self.request.method == 'GET':
            return [AllowAny()]
        return [IsAdminUser()]

    @extend_schema(
        tags=['Site Config'],
        summary='Get contact information',
        responses={200: ContactInfoSerializer},
    )
    def get(self, request):
        info = ContactInfo.load()
        return Response(ContactInfoSerializer(info).data)

    @extend_schema(
        tags=['Site Config'],
        summary='Update contact information',
        request=ContactInfoUpdateSerializer,
        responses={
            200: ContactInfoSerializer,
            400: OpenApiResponse(description='Validation error.'),
            403: OpenApiResponse(description='Admin access required.'),
        },
    )
    def patch(self, request):
        info = ContactInfo.load()
        serializer = ContactInfoUpdateSerializer(info, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(ContactInfoSerializer(info).data)


# ──────────────────────────────────────────────
# Contact Messages
# ──────────────────────────────────────────────

class ContactMessageCreateView(APIView):
    """
    POST /api/site/contact/   → public — submit a contact form message
    """
    permission_classes = [AllowAny]

    @extend_schema(
        tags=['Site Config'],
        summary='Submit a contact message',
        request=ContactMessageCreateSerializer,
        responses={
            201: OpenApiResponse(description='Message received.'),
            400: OpenApiResponse(description='Validation error.'),
        },
    )
    def post(self, request):
        serializer = ContactMessageCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        msg = serializer.save()

        # Dispatch Celery task in a daemon thread so the HTTP response is never
        # delayed by a Redis connection attempt (e.g. broker not running).
        import threading

        def _dispatch():
            try:
                from .tasks import notify_new_contact_message
                notify_new_contact_message.delay(msg.pk)
            except Exception:
                pass

        threading.Thread(target=_dispatch, daemon=True).start()

        return Response(
            {'detail': "Message received. We'll get back to you within 24 hours."},
            status=status.HTTP_201_CREATED,
        )


class ContactMessageListView(generics.ListAPIView):
    """
    GET /api/site/contact/messages/   → admin — list all messages
    """
    permission_classes = [IsAdminUser]
    serializer_class = ContactMessageSerializer
    queryset = ContactMessage.objects.all()

    @extend_schema(
        tags=['Site Config'],
        summary='List contact messages',
        description='Returns all contact messages ordered by newest first. **Admin only.**',
        responses={200: ContactMessageSerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class ContactMessageUnreadCountView(APIView):
    """
    GET /api/site/contact/messages/unread-count/  → admin — count of new+unread messages
    """
    permission_classes = [IsAdminUser]

    @extend_schema(
        tags=['Site Config'],
        summary='Get unread message count',
        responses={200: {'type': 'object', 'properties': {'count': {'type': 'integer'}}}},
    )
    def get(self, request):
        count = ContactMessage.objects.filter(
            status__in=[ContactMessage.STATUS_NEW, ContactMessage.STATUS_UNREAD]
        ).count()
        return Response({'count': count})


class ContactMessageStatusView(APIView):
    """
    PATCH /api/site/contact/messages/<pk>/status/   → admin — update status
    """
    permission_classes = [IsAdminUser]

    @extend_schema(
        tags=['Site Config'],
        summary='Update message status',
        request=ContactMessageStatusSerializer,
        responses={
            200: ContactMessageSerializer,
            400: OpenApiResponse(description='Invalid status value.'),
            403: OpenApiResponse(description='Admin access required.'),
            404: OpenApiResponse(description='Message not found.'),
        },
    )
    def patch(self, request, pk):
        try:
            msg = ContactMessage.objects.get(pk=pk)
        except ContactMessage.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = ContactMessageStatusSerializer(msg, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(ContactMessageSerializer(msg).data)
