"""
accounts/admin_views.py

Admin-only management endpoints:

  Roles (Django Groups)
  GET  /api/admin/roles/               — list all roles
  POST /api/admin/roles/               — create role
  GET  /api/admin/roles/<id>/          — role detail
  PUT  /api/admin/roles/<id>/          — update role + permissions
  DEL  /api/admin/roles/<id>/          — delete role

  Permissions
  GET  /api/admin/permissions/         — list all Django permissions

  User management
  GET  /api/admin/users/               — list all users
  GET  /api/admin/users/<uuid>/        — user detail
  POST /api/admin/users/<uuid>/assign-role/   — assign role to user
  POST /api/admin/users/<uuid>/remove-role/   — remove role from user
  PATCH /api/admin/users/<uuid>/              — toggle is_staff / is_active

  Content (admin sees everything)
  GET  /api/admin/artworks/            — all artworks (with filters)
  GET  /api/admin/orders/              — all orders (with filters)
  GET  /api/admin/orders/<uuid>/       — any order detail
  PUT  /api/admin/orders/<uuid>/status/— update order status
  GET  /api/admin/carts/               — all cart items

All endpoints require is_staff or is_superuser.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from drf_spectacular.utils import extend_schema, OpenApiResponse

from .permissions import IsAdminOrStaff
from .admin_serializers import (
    RoleSerializer,
    RoleWriteSerializer,
    PermissionSerializer,
    AssignRoleSerializer,
    AdminUserSerializer,
    AdminUserUpdateSerializer,
)
from apps.artworks.models import Artwork
from apps.artworks.serializers import ArtworkSerializer, UpdateArtworkSerializer
from apps.orders.models import Order
from apps.orders.serializers import OrderSerializer, UpdateOrderStatusSerializer
from apps.cart.models import CartItem
from apps.cart.serializers import CartItemSerializer
from apps.activity_logs.utils import log_activity

User = get_user_model()


# ─── Roles ───────────────────────────────────────────────────────────────────

class RoleListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOrStaff]

    @extend_schema(tags=['Admin — Roles'], summary='List all roles', responses={200: RoleSerializer(many=True)})
    def get(self, request):
        roles = Group.objects.prefetch_related('permissions').all()
        return Response(RoleSerializer(roles, many=True).data)

    @extend_schema(tags=['Admin — Roles'], summary='Create a role', request=RoleWriteSerializer, responses={201: RoleSerializer})
    def post(self, request):
        serializer = RoleWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        role = serializer.save()
        log_activity(user=request.user, subject=role,
                     description=f'Created role "{role.name}"', log_name='admin', event='role_created')
        return Response(RoleSerializer(role).data, status=status.HTTP_201_CREATED)


class RoleDetailView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOrStaff]

    def _get_role(self, pk):
        return get_object_or_404(Group.objects.prefetch_related('permissions'), pk=pk)

    @extend_schema(tags=['Admin — Roles'], summary='Get role detail', responses={200: RoleSerializer})
    def get(self, request, pk):
        return Response(RoleSerializer(self._get_role(pk)).data)

    @extend_schema(tags=['Admin — Roles'], summary='Update role name and permissions',
                   request=RoleWriteSerializer, responses={200: RoleSerializer})
    def put(self, request, pk):
        role = self._get_role(pk)
        serializer = RoleWriteSerializer(role, data=request.data)
        serializer.is_valid(raise_exception=True)
        role = serializer.save()
        log_activity(user=request.user, subject=role,
                     description=f'Updated role "{role.name}"', log_name='admin', event='role_updated')
        return Response(RoleSerializer(role).data)

    @extend_schema(tags=['Admin — Roles'], summary='Delete a role', responses={204: None})
    def delete(self, request, pk):
        role = self._get_role(pk)
        name = role.name
        role.delete()
        log_activity(user=request.user, description=f'Deleted role "{name}"', log_name='admin', event='role_deleted')
        return Response(status=status.HTTP_204_NO_CONTENT)


# ─── Permissions ─────────────────────────────────────────────────────────────

class PermissionListView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOrStaff]

    @extend_schema(tags=['Admin — Roles'], summary='List all available permissions',
                   responses={200: PermissionSerializer(many=True)})
    def get(self, request):
        perms = Permission.objects.select_related('content_type').order_by('content_type__app_label', 'codename')
        return Response(PermissionSerializer(perms, many=True).data)


# ─── Users ───────────────────────────────────────────────────────────────────

class AdminUserListView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOrStaff]

    @extend_schema(tags=['Admin — Users'], summary='List all users', responses={200: AdminUserSerializer(many=True)})
    def get(self, request):
        users = User.objects.prefetch_related('groups', 'user_permissions').all()
        search = request.query_params.get('search')
        if search:
            users = users.filter(name__icontains=search) | users.filter(email__icontains=search)
        return Response(AdminUserSerializer(users, many=True).data)


class AdminUserDetailView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOrStaff]

    def _get_user(self, uuid):
        return get_object_or_404(User.objects.prefetch_related('groups', 'user_permissions'), uuid=uuid)

    @extend_schema(tags=['Admin — Users'], summary='Get user detail', responses={200: AdminUserSerializer})
    def get(self, request, uuid):
        return Response(AdminUserSerializer(self._get_user(uuid)).data)

    @extend_schema(
        tags=['Admin — Users'],
        summary='Update user details (name, email, phone, is_staff, is_active)',
        request=AdminUserUpdateSerializer,
        responses={200: AdminUserSerializer},
    )
    def patch(self, request, uuid):
        user = self._get_user(uuid)
        serializer = AdminUserUpdateSerializer(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated_user = serializer.save()
        log_activity(
            user=request.user,
            subject=updated_user,
            description=f'Admin updated details for user {updated_user.email or updated_user.name}',
            log_name='admin',
            event='user_updated',
        )
        return Response(AdminUserSerializer(updated_user).data)


class AdminAssignRoleView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOrStaff]

    @extend_schema(tags=['Admin — Users'], summary='Assign a role to a user',
                   request=AssignRoleSerializer, responses={200: AdminUserSerializer})
    def post(self, request, uuid):
        user = get_object_or_404(User, uuid=uuid)
        serializer = AssignRoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        role_name = serializer.validated_data['role_name']
        user.assign_role(role_name)
        log_activity(user=request.user, subject=user,
                     description=f'Assigned role "{role_name}" to {user.email or user.name}',
                     log_name='admin', event='role_assigned')
        return Response(AdminUserSerializer(user).data)


class AdminRemoveRoleView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOrStaff]

    @extend_schema(tags=['Admin — Users'], summary='Remove a role from a user',
                   request=AssignRoleSerializer, responses={200: AdminUserSerializer})
    def post(self, request, uuid):
        user = get_object_or_404(User, uuid=uuid)
        serializer = AssignRoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        role_name = serializer.validated_data['role_name']
        group = Group.objects.filter(name=role_name).first()
        if group:
            user.groups.remove(group)
        log_activity(user=request.user, subject=user,
                     description=f'Removed role "{role_name}" from {user.email or user.name}',
                     log_name='admin', event='role_removed')
        return Response(AdminUserSerializer(user).data)


class AdminVerifyUserView(APIView):
    """
    POST  /api/admin/users/<uuid>/verify/   — manually mark verified_at = now
    DELETE /api/admin/users/<uuid>/verify/  — clear verified_at (unverify)
    """
    permission_classes = [IsAuthenticated, IsAdminOrStaff]

    @extend_schema(tags=['Admin — Users'], summary='Manually verify a user account',
                   responses={200: AdminUserSerializer})
    def post(self, request, uuid):
        from django.utils import timezone
        user = get_object_or_404(User, uuid=uuid)
        if user.verified_at:
            return Response({'detail': 'User is already verified.'}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        user.verified_at = timezone.now()
        user.save(update_fields=['verified_at'])
        log_activity(user=request.user, subject=user,
                     description=f'Admin manually verified account for {user.email or user.name}',
                     log_name='admin', event='user_verified')
        return Response(AdminUserSerializer(user).data)

    @extend_schema(tags=['Admin — Users'], summary='Revoke verification of a user account',
                   responses={200: AdminUserSerializer})
    def delete(self, request, uuid):
        user = get_object_or_404(User, uuid=uuid)
        if not user.verified_at:
            return Response({'detail': 'User is not verified.'}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        user.verified_at = None
        user.save(update_fields=['verified_at'])
        log_activity(user=request.user, subject=user,
                     description=f'Admin revoked verification for {user.email or user.name}',
                     log_name='admin', event='user_unverified')
        return Response(AdminUserSerializer(user).data)


# ─── Admin: All Artworks ──────────────────────────────────────────────────────

class AdminArtworkListView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOrStaff]

    @extend_schema(tags=['Admin — Content'], summary='List all artworks (admin)',
                   responses={200: ArtworkSerializer(many=True)})
    def get(self, request):
        qs = Artwork.objects.select_related('category').all()
        search = request.query_params.get('search')
        if search:
            qs = qs.filter(name__icontains=search)
        is_sold = request.query_params.get('is_sold')
        if is_sold is not None:
            qs = qs.filter(is_sold=is_sold.lower() == 'true')
        category = request.query_params.get('category_uuid')
        if category:
            qs = qs.filter(category__uuid=category)
        return Response(ArtworkSerializer(qs, many=True, context={'request': request}).data)


class AdminArtworkDetailView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOrStaff]

    def _get(self, uuid):
        return get_object_or_404(Artwork.objects.select_related('category'), uuid=uuid)

    @extend_schema(tags=['Admin — Content'], summary='Get any artwork (admin)', responses={200: ArtworkSerializer})
    def get(self, request, uuid):
        return Response(ArtworkSerializer(self._get(uuid), context={'request': request}).data)

    @extend_schema(tags=['Admin — Content'], summary='Update any artwork (admin)',
                   request=UpdateArtworkSerializer, responses={200: ArtworkSerializer})
    def put(self, request, uuid):
        artwork = self._get(uuid)
        serializer = UpdateArtworkSerializer(artwork, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        artwork = serializer.save()
        log_activity(user=request.user, subject=artwork,
                     description=f'Admin updated artwork "{artwork.name}"',
                     log_name='artworks', event='updated')
        return Response(ArtworkSerializer(artwork, context={'request': request}).data)

    @extend_schema(tags=['Admin — Content'], summary='Delete any artwork (admin)', responses={204: None})
    def delete(self, request, uuid):
        artwork = self._get(uuid)
        name = artwork.name
        artwork.delete()
        log_activity(user=request.user, description=f'Admin deleted artwork "{name}"',
                     log_name='artworks', event='deleted')
        return Response(status=status.HTTP_204_NO_CONTENT)


# ─── Admin: All Orders ────────────────────────────────────────────────────────

class AdminOrderListView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOrStaff]

    @extend_schema(tags=['Admin — Content'], summary='List all orders (admin)',
                   responses={200: OrderSerializer(many=True)})
    def get(self, request):
        qs = Order.objects.select_related('user').prefetch_related('items').all()
        status_filter = request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        user_email = request.query_params.get('user_email')
        if user_email:
            qs = qs.filter(user__email__icontains=user_email)
        return Response(OrderSerializer(qs, many=True).data)


class AdminOrderDetailView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOrStaff]

    @extend_schema(tags=['Admin — Content'], summary='Get any order detail (admin)', responses={200: OrderSerializer})
    def get(self, request, uuid):
        order = get_object_or_404(Order.objects.prefetch_related('items'), uuid=uuid)
        return Response(OrderSerializer(order).data)


class AdminOrderStatusView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOrStaff]

    @extend_schema(tags=['Admin — Content'], summary='Update order status (admin)',
                   request=UpdateOrderStatusSerializer, responses={200: OrderSerializer})
    def put(self, request, uuid):
        from apps.notifications.tasks import notify_async
        order = get_object_or_404(Order, uuid=uuid)
        serializer = UpdateOrderStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        old_status = order.status
        order.status = serializer.validated_data['status']
        order.save(update_fields=['status', 'updated_at'])

        notify_async(
            user_id=order.user.pk,
            subject=f'Your order status has been updated to {order.get_status_display()}',
            message=f'Hi {order.user.name}, your order #{order.id} status changed to {order.status}.',
        )
        log_activity(user=request.user, subject=order,
                     description=f'Order #{order.id} status: {old_status} → {order.status}',
                     log_name='orders', event='order_status_updated')
        return Response(OrderSerializer(order).data)


# ─── Admin: All Cart Items ────────────────────────────────────────────────────

class AdminCartListView(APIView):
    permission_classes = [IsAuthenticated, IsAdminOrStaff]

    @extend_schema(tags=['Admin — Content'], summary='List all cart items (admin)',
                   responses={200: CartItemSerializer(many=True)})
    def get(self, request):
        qs = CartItem.objects.select_related('cart__user', 'artwork').all()
        user_email = request.query_params.get('user_email')
        if user_email:
            qs = qs.filter(cart__user__email__icontains=user_email)
        source = request.query_params.get('source')
        if source:
            qs = qs.filter(source=source)
        return Response(CartItemSerializer(qs, many=True, context={'request': request}).data)
