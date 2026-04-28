"""
accounts/views.py
Equivalent to Laravel's AuthController + ProfileController.
"""

import random
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone
from rest_framework import serializers as drf_serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from drf_spectacular.utils import (
    extend_schema,
    inline_serializer,
    OpenApiExample,
    OpenApiResponse,
)

from apps.activity_logs.utils import log_activity
from .tasks import dispatch_verification_otp, dispatch_password_reset_otp
from .models import Profile
from .serializers import (
    RegisterSerializer,
    VerifyAccountSerializer,
    ResendVerificationSerializer,
    LoginSerializer,
    ForgotPasswordSerializer,
    ResetPasswordSerializer,
    UserSerializer,
    ProfileSerializer,
    UpdateProfileSerializer,
    UpdateUserSerializer,
)

User = get_user_model()

# ─── Reusable inline schemas ────────────────────────────────────────────────

_MessageSchema = inline_serializer(
    'MessageResponse',
    fields={'message': drf_serializers.CharField()},
)

_TokenSchema = inline_serializer(
    'TokenResponse',
    fields={
        'access_token':  drf_serializers.CharField(),
        'refresh_token': drf_serializers.CharField(),
        'token_type':    drf_serializers.CharField(default='Bearer'),
        'user':          UserSerializer(),
    },
)

_ProfileUpdateResponseSchema = inline_serializer(
    'ProfileUpdateResponse',
    fields={
        'message': drf_serializers.CharField(),
        'data':    ProfileSerializer(),
    },
)




# ────────────────────────────────────────────────────────
# Auth Views
# ────────────────────────────────────────────────────────

class RegisterView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=['Auth'],
        summary='Register a new user',
        description=(
            'Creates a new user account and sends a 6-digit OTP to the provided '
            'email or phone for verification.'
        ),
        request=RegisterSerializer,
        responses={
            201: OpenApiResponse(
                response=_MessageSchema,
                description='Account created — OTP sent to email or phone.',
                examples=[
                    OpenApiExample(
                        'Success',
                        value={'message': 'Account created. Please check your email for the verification code.'},
                    )
                ],
            ),
            422: OpenApiResponse(description='Validation error (duplicate email/phone or missing contact).'),
        },
        examples=[
            OpenApiExample(
                'Email registration',
                request_only=True,
                value={'name': 'Jane Doe', 'email': 'jane@example.com', 'password': 'secret123'},
            ),
            OpenApiExample(
                'Phone registration',
                request_only=True,
                value={'name': 'John Doe', 'phone': '+255712345678', 'password': 'secret123'},
            ),
        ],
    )
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        code = str(random.randint(100000, 999999))

        user = User.objects.create_user(
            name=data['name'],
            email=data.get('email'),
            phone=data.get('phone'),
            password=data['password'],
            verification_code=code,
        )

        channel = 'email' if user.email else 'phone'
        dispatch_verification_otp(user.pk, code)

        return Response(
            {'message': f'Account created. Please check your {channel} for the verification code.'},
            status=status.HTTP_201_CREATED,
        )


class VerifyAccountView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=['Auth'],
        summary='Verify account with OTP',
        description=(
            'Validates the 6-digit OTP sent during registration. '
            'On success the account is activated and the **Bidder** role is assigned.'
        ),
        request=VerifyAccountSerializer,
        responses={
            200: OpenApiResponse(
                response=inline_serializer(
                    'VerifyResponse',
                    fields={
                        'message': drf_serializers.CharField(),
                        'user':    UserSerializer(),
                    },
                ),
                description='Account verified successfully.',
            ),
            422: OpenApiResponse(description='Invalid or expired OTP code.'),
        },
        examples=[
            OpenApiExample(
                'Verify by email',
                request_only=True,
                value={'identifier': 'jane@example.com', 'code': '482910'},
            ),
        ],
    )
    def post(self, request):
        serializer = VerifyAccountSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        identifier = serializer.validated_data['identifier']
        code = serializer.validated_data['code']

        user = User.objects.filter(email=identifier).first() \
            or User.objects.filter(phone=identifier).first()

        if not user or user.verification_code != code:
            return Response({'message': 'Invalid or expired code.'}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        now = timezone.now()
        user.verified_at = now
        if identifier == user.email:
            user.email_verified_at = now
        elif identifier == user.phone:
            user.phone_verified_at = now

        user.verification_code = None
        user.save()

        user.assign_role('Bidder')

        log_activity(
            user=user,
            description='Account verified and Bidder role assigned',
            log_name='auth',
            event='verified',
        )

        return Response({'message': 'Account activated. You can now bid!', 'user': UserSerializer(user).data})


class ResendVerificationView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=['Auth'],
        summary='Resend account verification OTP',
        description='Generates and sends a fresh 6-digit verification code for an unverified account.',
        request=ResendVerificationSerializer,
        responses={
            200: OpenApiResponse(response=_MessageSchema, description='Verification code sent.'),
            404: OpenApiResponse(description='Account not found.'),
            422: OpenApiResponse(description='Account is already verified.'),
            429: OpenApiResponse(description='Please wait before requesting another code.'),
        },
        examples=[
            OpenApiExample(
                'Resend by email',
                request_only=True,
                value={'identifier': 'jane@example.com'},
            ),
        ],
    )
    def post(self, request):
        serializer = ResendVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        identifier = serializer.validated_data['identifier']

        user = User.objects.filter(email=identifier).first() \
            or User.objects.filter(phone=identifier).first()

        if not user:
            return Response({'message': 'Account not found.'}, status=status.HTTP_404_NOT_FOUND)

        if user.verified_at:
            return Response({'message': 'This account is already verified.'}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        cooldown_key = f'verification_resend:{user.pk}'
        if cache.get(cooldown_key):
            return Response(
                {'message': 'Please wait a minute before requesting another code.'},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        code = str(random.randint(100000, 999999))
        user.verification_code = code
        user.save(update_fields=['verification_code', 'updated_at'])
        cache.set(cooldown_key, True, 60)

        dispatch_verification_otp(user.pk, code)
        channel = 'email' if user.email else 'phone'

        log_activity(
            user=user,
            description='Verification code resent',
            log_name='auth',
            event='verification_code_resent',
        )

        return Response({'message': f'A new verification code has been sent to your {channel}.'})


class LoginView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=['Auth'],
        summary='Login and obtain JWT tokens',
        description=(
            'Authenticates a user by email **or** phone number and returns '
            'a JWT access token (short-lived) and a refresh token (long-lived).'
        ),
        request=LoginSerializer,
        responses={
            200: OpenApiResponse(
                response=_TokenSchema,
                description='Login successful — tokens returned.',
                examples=[
                    OpenApiExample(
                        'Success',
                        value={
                            'access_token': 'eyJ0eXAiOiJKV1Q...',
                            'refresh_token': 'eyJ0eXAiOiJKV1Q...',
                            'token_type': 'Bearer',
                            'user': {
                                'uuid': 'a1b2c3d4-...',
                                'name': 'Jane Doe',
                                'email': 'jane@example.com',
                                'phone': None,
                                'verified_at': '2026-01-01T00:00:00Z',
                                'roles': ['Bidder'],
                                'permissions': [],
                            },
                        },
                    )
                ],
            ),
            401: OpenApiResponse(description='Invalid credentials.'),
            403: OpenApiResponse(description='Account not yet verified.'),
        },
        examples=[
            OpenApiExample(
                'Login by email',
                request_only=True,
                value={'login': 'jane@example.com', 'password': 'secret123'},
            ),
            OpenApiExample(
                'Login by phone',
                request_only=True,
                value={'login': '+255712345678', 'password': 'secret123'},
            ),
        ],
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        login = serializer.validated_data['login']
        password = serializer.validated_data['password']

        user = User.objects.filter(email=login).first() \
            or User.objects.filter(phone=login).first()

        if not user or not user.check_password(password):
            return Response({'message': 'Invalid credentials.'}, status=status.HTTP_401_UNAUTHORIZED)

        if not user.is_verified():
            return Response(
                {'message': 'Account not activated. Please verify your email/phone first.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        refresh = RefreshToken.for_user(user)

        log_activity(
            user=user,
            description='User logged into the system',
            log_name='auth',
            event='login',
            properties={'ip': request.META.get('REMOTE_ADDR', '')},
        )

        return Response({
            'access_token': str(refresh.access_token),
            'refresh_token': str(refresh),
            'token_type': 'Bearer',
            'user': UserSerializer(user).data,
        })


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['Auth'],
        summary='Logout — blacklist the refresh token',
        description=(
            'Blacklists the provided refresh token so it can no longer be used '
            'to obtain new access tokens. Equivalent to deleting a Sanctum token.'
        ),
        request=inline_serializer(
            'LogoutRequest',
            fields={'refresh_token': drf_serializers.CharField()},
        ),
        responses={
            200: OpenApiResponse(
                response=_MessageSchema,
                description='Logged out successfully.',
                examples=[
                    OpenApiExample('Success', value={'message': 'Logged out successfully.'})
                ],
            ),
        },
        examples=[
            OpenApiExample(
                'Logout',
                request_only=True,
                value={'refresh_token': 'eyJ0eXAiOiJKV1Q...'},
            ),
        ],
    )
    def post(self, request):
        refresh_token = request.data.get('refresh_token')
        if refresh_token:
            try:
                token = RefreshToken(refresh_token)
                token.blacklist()
            except TokenError:
                pass

        log_activity(
            user=request.user,
            description='User logged out of the system',
            log_name='auth',
            event='logout',
            properties={'ip': request.META.get('REMOTE_ADDR', '')},
        )

        return Response({'message': 'Logged out successfully.'})


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['Auth'],
        summary='Get the authenticated user',
        description='Returns the full profile of the currently authenticated user including roles and permissions.',
        responses={
            200: OpenApiResponse(response=UserSerializer, description='Authenticated user data.'),
            401: OpenApiResponse(description='Not authenticated.'),
        },
    )
    def get(self, request):
        return Response(UserSerializer(request.user).data)


class UpdateMeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['Auth'],
        summary='Update own account details (name, email, phone)',
        description='Allows the authenticated user to update their own name, email, or phone number.',
        request=UpdateUserSerializer,
        responses={200: OpenApiResponse(response=UserSerializer, description='Updated user.')},
    )
    def patch(self, request):
        serializer = UpdateUserSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        log_activity(
            user=user,
            description='Updated own account details',
            log_name='auth',
            event='profile_updated',
        )
        return Response(UserSerializer(user).data)


class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=['Auth'],
        summary='Request a password-reset OTP',
        description=(
            'Sends a 6-digit reset code to the registered email or phone. '
            'Always returns **200** to prevent user enumeration.'
        ),
        request=ForgotPasswordSerializer,
        responses={
            200: OpenApiResponse(
                response=_MessageSchema,
                description='OTP dispatched (or silently ignored if account not found).',
                examples=[
                    OpenApiExample(
                        'Success',
                        value={'message': 'Reset code sent to your registered contact.'},
                    )
                ],
            ),
        },
        examples=[
            OpenApiExample(
                'By email',
                request_only=True,
                value={'login': 'jane@example.com'},
            ),
        ],
    )
    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        login = serializer.validated_data['login']

        user = User.objects.filter(email=login).first() \
            or User.objects.filter(phone=login).first()

        if not user:
            return Response({'message': 'If this account exists, an OTP has been sent.'})

        code = str(random.randint(100000, 999999))
        user.verification_code = code
        user.save(update_fields=['verification_code'])

        log_activity(user=user, description='Requested a password reset OTP', log_name='auth', event='forgot_password')
        dispatch_password_reset_otp(user.pk, code)

        return Response({'message': 'Reset code sent to your registered contact.'})


class ResetPasswordView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=['Auth'],
        summary='Reset password using OTP',
        description='Validates the OTP and sets a new password for the account.',
        request=ResetPasswordSerializer,
        responses={
            200: OpenApiResponse(
                response=_MessageSchema,
                description='Password reset successfully.',
                examples=[
                    OpenApiExample(
                        'Success',
                        value={'message': 'Password reset successful. Please login with your new password.'},
                    )
                ],
            ),
            422: OpenApiResponse(description='Invalid/expired code or passwords do not match.'),
        },
        examples=[
            OpenApiExample(
                'Reset password',
                request_only=True,
                value={
                    'login': 'jane@example.com',
                    'code': '482910',
                    'password': 'newSecret123',
                    'password_confirmation': 'newSecret123',
                },
            ),
        ],
    )
    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user = User.objects.filter(email=data['login']).first() \
            or User.objects.filter(phone=data['login']).first()

        if not user or user.verification_code != data['code']:
            return Response({'message': 'Invalid or expired code.'}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        user.set_password(data['password'])
        user.verification_code = None
        user.save()

        log_activity(user=user, description='Successfully reset their password', log_name='auth', event='reset_password')

        return Response({'message': 'Password reset successful. Please login with your new password.'})


# ────────────────────────────────────────────────────────
# Profile Views
# ────────────────────────────────────────────────────────

class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['Profile'],
        summary='Get authenticated user\'s profile',
        description='Returns the profile details (bio, avatar, address, city) for the logged-in user.',
        responses={
            200: OpenApiResponse(response=ProfileSerializer, description='Profile data.'),
            404: OpenApiResponse(description='Profile not found.'),
        },
    )
    def get(self, request):
        profile = getattr(request.user, 'profile', None)
        if not profile:
            return Response({'message': 'Profile not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(ProfileSerializer(profile, context={'request': request}).data)

    @extend_schema(
        tags=['Profile'],
        summary='Create or update profile',
        description=(
            'Creates the profile if it does not exist, otherwise updates it. '
            'Send `multipart/form-data` when uploading an avatar image.'
        ),
        request=UpdateProfileSerializer,
        responses={
            200: OpenApiResponse(
                response=_ProfileUpdateResponseSchema,
                description='Profile saved successfully.',
                examples=[
                    OpenApiExample(
                        'Success',
                        value={
                            'message': 'Profile updated successfully.',
                            'data': {
                                'uuid': 'a1b2c3d4-...',
                                'bio': 'Digital artist from Dar es Salaam.',
                                'avatar_url': 'http://localhost:8000/media/avatars/me.jpg',
                                'address': 'Mikocheni B',
                                'city': 'Dar es Salaam',
                                'created_at': '2026-01-01T00:00:00Z',
                                'updated_at': '2026-04-08T12:00:00Z',
                            },
                        },
                    )
                ],
            ),
        },
        examples=[
            OpenApiExample(
                'Update profile (JSON)',
                request_only=True,
                value={'bio': 'Digital artist from Dar es Salaam.', 'city': 'Dar es Salaam', 'address': 'Mikocheni B'},
            ),
        ],
    )
    def post(self, request):
        user = request.user
        profile = getattr(user, 'profile', None)

        serializer = UpdateProfileSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        avatar = data.pop('avatar', None)

        if avatar:
            if profile and profile.avatar:
                profile.avatar.delete(save=False)
            data['avatar'] = avatar

        if profile:
            for attr, val in data.items():
                setattr(profile, attr, val)
            profile.save()
        else:
            profile = Profile.objects.create(user=user, **data)

        return Response({
            'message': 'Profile updated successfully.',
            'data': ProfileSerializer(profile, context={'request': request}).data,
        })


class RemoveAvatarView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['Profile'],
        summary='Remove profile avatar',
        description='Deletes the current avatar image from storage and clears the avatar field.',
        responses={
            200: OpenApiResponse(
                response=_MessageSchema,
                description='Avatar removed.',
                examples=[OpenApiExample('Removed', value={'message': 'Avatar removed.'})],
            ),
            404: OpenApiResponse(
                description='No avatar to remove.',
                examples=[OpenApiExample('Not found', value={'message': 'No avatar to remove.'})],
            ),
        },
    )
    def delete(self, request):
        profile = getattr(request.user, 'profile', None)
        if profile and profile.avatar:
            profile.avatar.delete(save=False)
            profile.avatar = None
            profile.save(update_fields=['avatar'])
            return Response({'message': 'Avatar removed.'})
        return Response({'message': 'No avatar to remove.'}, status=status.HTTP_404_NOT_FOUND)


# ── Address views ─────────────────────────────────────────────────────────────

from .models import Address
from .serializers import AddressSerializer, AddressWriteSerializer


class AddressListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Addresses'], summary='List my addresses', responses={200: AddressSerializer(many=True)})
    def get(self, request):
        qs = Address.objects.filter(user=request.user)
        return Response(AddressSerializer(qs, many=True).data)

    @extend_schema(tags=['Addresses'], summary='Add a new address',
                   request=AddressWriteSerializer, responses={201: AddressSerializer})
    def post(self, request):
        ser = AddressWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        is_first = not Address.objects.filter(user=request.user).exists()
        obj = ser.save(user=request.user, is_default=is_first)
        return Response(AddressSerializer(obj).data, status=status.HTTP_201_CREATED)


class AddressDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get(self, request, pk):
        from django.shortcuts import get_object_or_404
        return get_object_or_404(Address, pk=pk, user=request.user)

    @extend_schema(tags=['Addresses'], summary='Update an address',
                   request=AddressWriteSerializer, responses={200: AddressSerializer})
    def patch(self, request, pk):
        obj = self._get(request, pk)
        ser = AddressWriteSerializer(obj, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(AddressSerializer(obj).data)

    @extend_schema(tags=['Addresses'], summary='Delete an address', responses={204: None})
    def delete(self, request, pk):
        obj = self._get(request, pk)
        was_default = obj.is_default
        obj.delete()
        if was_default:
            next_addr = Address.objects.filter(user=request.user).first()
            if next_addr:
                next_addr.set_as_default()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AddressSetDefaultView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['Addresses'], summary='Set an address as default', responses={200: AddressSerializer})
    def post(self, request, pk):
        from django.shortcuts import get_object_or_404
        obj = get_object_or_404(Address, pk=pk, user=request.user)
        obj.set_as_default()
        return Response(AddressSerializer(obj).data)
