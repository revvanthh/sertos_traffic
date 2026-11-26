"""
Authentication and User Profile Views for SERTOS Emergency Response System.

Implements:
1. LoginView (POST /api/auth/login/) - Custom token issuance with verification gate.
2. TokenRefreshView (POST /api/auth/token/refresh/) - Access token renewal.
3. LogoutView (POST /api/auth/logout/) - User-validated token blacklisting.
4. RegisterView (POST /api/auth/register/) - Controlled driver registration.
5. ProfileView (GET/PATCH /api/auth/profile/) - Authenticated profile inspection & update.

Enforces:
- Strict project-wide standard JSON response envelope.
- Explicit DRF permission classes overriding project-level defaults.
"""

from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, serializers
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView as SimpleJWTTokenRefreshView,
)
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import (
    InvalidToken,
    TokenError,
)

from apps.accounts.permissions import IsSystemAdmin
from apps.emergencies.models import Ambulance, Hospital
from apps.traffic.models import CommandStatus, TrafficCommand, TrafficDevice
from apps.traffic.serializers import TrafficCommandSerializer

from .serializers import (
    CustomTokenObtainPairSerializer,
    CustomTokenRefreshSerializer,
    UserRegistrationSerializer,
    UserProfileSerializer,
)


def standard_response(
    data=None,
    message="Operation completed successfully.",
    status_code=status.HTTP_200_OK,
    success=True,
    errors=None,
):
    """
    Constructs a uniform JSON response envelope across all SERTOS endpoints.
    """
    payload = {
        "success": success,
        "data": data if data is not None else {},
        "message": message,
        "timestamp": timezone.now().isoformat(),
    }
    if errors is not None:
        payload["errors"] = errors
    return Response(payload, status=status_code)


class AdminOverviewView(APIView):
    """Return the limited personnel and fleet data needed by the admin dashboard."""

    permission_classes = [IsAuthenticated, IsSystemAdmin]

    def get(self, request):
        User = get_user_model()
        users = User.objects.order_by("-date_joined")[:100]
        ambulances = Ambulance.objects.select_related("assigned_driver").order_by("vehicle_number")[:100]

        data = {
            "summary": {
                "registered_users": User.objects.count(),
                "pending_verification": User.objects.filter(is_verified=False).count(),
                "active_ambulances": Ambulance.objects.filter(is_active=True).count(),
                "active_hospitals": Hospital.objects.filter(is_active=True).count(),
                "active_junctions": TrafficDevice.objects.filter(is_active=True).count(),
                "pending_commands": TrafficCommand.objects.filter(status=CommandStatus.PENDING).count(),
            },
            "users": [
                {
                    "id": user.id,
                    "username": user.username,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "email": user.email,
                    "role": user.role,
                    "is_verified": user.is_verified,
                    "is_active": user.is_active,
                    "date_joined": user.date_joined,
                }
                for user in users
            ],
            "ambulances": [
                {
                    "id": str(ambulance.id),
                    "vehicle_number": ambulance.vehicle_number,
                    "vehicle_type": ambulance.vehicle_type,
                    "is_available": ambulance.is_available,
                    "is_active": ambulance.is_active,
                    "assigned_driver": ambulance.assigned_driver.username if ambulance.assigned_driver else None,
                }
                for ambulance in ambulances
            ],
            "commands": TrafficCommandSerializer(
                TrafficCommand.objects.select_related("device", "incident").order_by("-created_at")[:50],
                many=True,
            ).data,
        }
        return standard_response(data=data, message="Administrator overview retrieved successfully.")


class UserVerificationSerializer(serializers.Serializer):
    is_verified = serializers.BooleanField()


class UserVerificationView(APIView):
    """Allow administrators to verify a public driver registration."""

    permission_classes = [IsAuthenticated, IsSystemAdmin]

    def patch(self, request, user_id):
        serializer = UserVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = get_object_or_404(get_user_model(), pk=user_id)
        user.is_verified = serializer.validated_data["is_verified"]
        user.save(update_fields=["is_verified"])

        data = {
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "is_verified": user.is_verified,
        }
        return standard_response(data=data, message="Account verification updated successfully.")


class LoginView(TokenObtainPairView):
    """
    POST /api/auth/login/
    Authenticates username and password; returns JWT access, refresh tokens, and user claims.
    Rejects inactive and unverified accounts with HTTP 401.
    """

    permission_classes = [AllowAny]
    serializer_class = CustomTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except AuthenticationFailed as exc:
            msg = str(exc.detail) if hasattr(exc, "detail") else str(exc)
            return standard_response(
                success=False,
                errors={"detail": [msg]},
                message=msg,
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        except TokenError as exc:
            return standard_response(
                success=False,
                errors={"detail": [str(exc)]},
                message="Authentication failed during token generation.",
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        except serializers.ValidationError as exc:
            return standard_response(
                success=False,
                errors=exc.detail,
                message="Invalid request data.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        return standard_response(
            data=serializer.validated_data,
            message="Authentication successful.",
            status_code=status.HTTP_200_OK,
        )


class TokenRefreshView(SimpleJWTTokenRefreshView):
    """
    POST /api/auth/token/refresh/
    Exchanges a valid refresh token for a newly issued access token.
    Respects refresh token rotation and blacklisting settings.
    Enforces live database verification check to reject unverified/revoked users.
    """

    permission_classes = [AllowAny]
    serializer_class = CustomTokenRefreshSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except AuthenticationFailed as exc:
            msg = str(exc.detail) if hasattr(exc, "detail") else str(exc)
            return standard_response(
                success=False,
                errors={"detail": [msg]},
                message=msg,
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        except (InvalidToken, TokenError) as exc:
            msg = "Token is invalid, expired, or blacklisted."
            return standard_response(
                success=False,
                errors={"detail": [msg]},
                message=msg,
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        except serializers.ValidationError as exc:
            return standard_response(
                success=False,
                errors=exc.detail,
                message="Refresh token validation failed.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        return standard_response(
            data=serializer.validated_data,
            message="Access token refreshed successfully.",
            status_code=status.HTTP_200_OK,
        )


class LogoutView(APIView):
    """
    POST /api/auth/logout/
    Blacklists the submitted refresh token.
    Enforces that the token's user_id claim matches request.user.pk.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        refresh_token_str = request.data.get("refresh")
        if not refresh_token_str:
            return standard_response(
                success=False,
                errors={"refresh": ["Refresh token is required for logout."]},
                message="Refresh token missing from request payload.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            token = RefreshToken(refresh_token_str)

            # Enforce user ownership: token must belong to request.user
            token_user_id = token.payload.get("user_id")
            if token_user_id is None or str(token_user_id) != str(request.user.pk):
                return standard_response(
                    success=False,
                    errors={
                        "detail": [
                            "Token does not belong to the authenticated user."
                        ]
                    },
                    message="Forbidden: Cannot blacklist tokens belonging to another user.",
                    status_code=status.HTTP_403_FORBIDDEN,
                )

            # Blacklist token
            token.blacklist()

        except (InvalidToken, TokenError):
            return standard_response(
                success=False,
                errors={
                    "detail": [
                        "Token is invalid, expired, or already blacklisted."
                    ]
                },
                message="Invalid or already invalidated refresh token.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )
        except Exception:
            return standard_response(
                success=False,
                errors={"detail": ["An error occurred during logout."]},
                message="Logout processing error.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        return standard_response(
            data={},
            message="Logged out successfully. Refresh token invalidated.",
            status_code=status.HTTP_200_OK,
        )


class RegisterView(APIView):
    """
    POST /api/auth/register/
    Controlled public self-registration.
    Creates unverified AMBULANCE_DRIVER accounts only.
    Prevents role escalation and self-verification.
    """

    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = UserRegistrationSerializer(data=request.data)
        if not serializer.is_valid():
            return standard_response(
                success=False,
                errors=serializer.errors,
                message="Registration failed due to validation errors.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        user = serializer.save()
        user_data = {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "phone_number": user.phone_number,
            "badge_or_employee_id": user.badge_or_employee_id,
            "is_verified": user.is_verified,
        }
        return standard_response(
            data=user_data,
            message="Account registered successfully. Awaiting administrative verification.",
            status_code=status.HTTP_201_CREATED,
        )


class ProfileView(APIView):
    """
    GET/PATCH /api/auth/profile/
    GET: Returns current authenticated user profile.
    PATCH: Allows updating approved fields (email, phone_number, badge_or_employee_id).
    Role, is_verified, and username are immutable.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        serializer = UserProfileSerializer(request.user)
        return standard_response(
            data=serializer.data,
            message="User profile retrieved successfully.",
            status_code=status.HTTP_200_OK,
        )

    def patch(self, request, *args, **kwargs):
        serializer = UserProfileSerializer(
            instance=request.user,
            data=request.data,
            partial=True,
        )
        if not serializer.is_valid():
            return standard_response(
                success=False,
                errors=serializer.errors,
                message="Profile update failed due to validation errors.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        updated_user = serializer.save()
        ambulance_number = str(request.data.get("badge_or_employee_id", "")).strip()
        if ambulance_number and getattr(updated_user, "role", None) == "AMBULANCE_DRIVER":
            from apps.emergencies.models import Ambulance

            ambulance = Ambulance.objects.filter(
                assigned_driver=updated_user,
                is_active=True,
            ).first()
            if ambulance and ambulance.vehicle_number != ambulance_number:
                ambulance.vehicle_number = ambulance_number
                try:
                    ambulance.save(update_fields=["vehicle_number"])
                except Exception:
                    return standard_response(
                        success=False,
                        errors={
                            "badge_or_employee_id": [
                                "Ambulance registration number is already in use."
                            ]
                        },
                        message="Profile update failed.",
                        status_code=status.HTTP_400_BAD_REQUEST,
                    )
        return standard_response(
            data=UserProfileSerializer(updated_user).data,
            message="Profile updated successfully.",
            status_code=status.HTTP_200_OK,
        )
