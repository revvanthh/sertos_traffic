"""
Serializers for SERTOS Authentication and User Management.

Enforces:
- Custom JWT claims (user_id, role, is_verified) via SimpleJWT.
- Rejection of unverified/inactive accounts during login.
- Privilege escalation prevention on self-registration (hardcoded role & is_verified=False).
- Read-only protection on critical profile fields (role, is_verified, is_staff, is_superuser, username).
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import (
    TokenObtainPairSerializer,
    TokenRefreshSerializer,
)
from rest_framework_simplejwt.exceptions import (
    AuthenticationFailed,
    InvalidToken,
    TokenError,
)

from .models import UserRole

User = get_user_model()


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Custom JWT Token serializer extending SimpleJWT's TokenObtainPairSerializer.
    - Adds custom claims (user_id, role, is_verified) to the token payload.
    - Rejects inactive accounts.
    - Rejects unverified accounts with AuthenticationFailed (401).
    - Does NOT expose passwords, phone numbers, or unnecessary personal info in claims.
    """

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        # Custom claims embedded directly in token payload
        token["user_id"] = user.id
        token["role"] = user.role
        token["is_verified"] = user.is_verified

        return token

    def validate(self, attrs):
        identifier = str(attrs.get("username", "")).strip()
        if identifier and "@" in identifier:
            matching_user = User.objects.filter(email__iexact=identifier).first()
            if matching_user:
                attrs = attrs.copy()
                attrs["username"] = matching_user.username

        data = super().validate(attrs)

        # Check account verification status
        if not self.user.is_verified:
            raise AuthenticationFailed(
                "Account is pending administrative verification. Access denied until approved."
            )

        # Append minimal user metadata to the login response payload
        data["user"] = {
            "id": self.user.id,
            "username": self.user.username,
            "role": self.user.role,
            "is_verified": self.user.is_verified,
        }

        return data


class CustomTokenRefreshSerializer(TokenRefreshSerializer):
    """
    Custom token refresh serializer that validates the requesting user's live database state
    before issuing a refreshed access token.
    Rejects revoked or unverified accounts with AuthenticationFailed (401).
    """

    def validate(self, attrs):
        refresh_str = attrs.get("refresh")
        try:
            refresh = self.token_class(refresh_str)
        except TokenError as exc:
            raise InvalidToken(exc.args[0])

        user_id = refresh.payload.get("user_id")
        if not user_id:
            raise InvalidToken("Token contained no recognizable user identification.")

        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            raise AuthenticationFailed("User account associated with this token no longer exists.")

        if not user.is_active:
            raise AuthenticationFailed("User account is inactive.")

        if not user.is_verified:
            raise AuthenticationFailed(
                "Account verification has been revoked or is pending administrative approval."
            )

        data = super().validate(attrs)
        return data


class UserRegistrationSerializer(serializers.ModelSerializer):
    """
    Serializer for controlled public self-registration.
    - Accepts ONLY: username, email, password, phone_number, badge_or_employee_id.
    - Enforces Django's password validators.
    - Uses set_password() for secure hashing.
    - Hardcodes role to AMBULANCE_DRIVER and is_verified to False.
    - Rejects/ignores any client-supplied role, is_verified, is_staff, or is_superuser.
    """

    password = serializers.CharField(
        write_only=True,
        required=True,
        style={"input_type": "password"},
        help_text="User password complying with Django password validation rules.",
    )

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "password",
            "phone_number",
            "badge_or_employee_id",
        )
        read_only_fields = ("id",)

    def validate_password(self, value):
        validate_password(value)
        return value

    def create(self, validated_data):
        password = validated_data.pop("password")

        # Hardcode non-privileged defaults to prevent privilege escalation
        user = User(
            username=validated_data.get("username"),
            email=validated_data.get("email", ""),
            phone_number=validated_data.get("phone_number", ""),
            badge_or_employee_id=validated_data.get("badge_or_employee_id", ""),
            role=UserRole.AMBULANCE_DRIVER,
            is_verified=False,
            is_staff=False,
            is_superuser=False,
        )
        user.set_password(password)
        user.save()
        return user


class UserProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for viewing and updating an authenticated user's profile.
    - Read-only fields: id, username, role, is_verified, is_staff, is_superuser, date_joined.
    - Writable fields: email, phone_number, badge_or_employee_id.
    - Never exposes password hashes or credentials.
    """

    ambulance_vehicle_number = serializers.SerializerMethodField()

    def get_ambulance_vehicle_number(self, user):
        if user.role != UserRole.AMBULANCE_DRIVER:
            return None
        from apps.emergencies.models import Ambulance

        ambulance = Ambulance.objects.filter(
            assigned_driver=user,
            is_active=True,
        ).order_by("vehicle_number").first()
        return ambulance.vehicle_number if ambulance else None

    def validate_age(self, value):
        if value is not None and (value < 18 or value > 100):
            raise serializers.ValidationError("Age must be between 18 and 100.")
        return value

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "age",
            "role",
            "phone_number",
            "badge_or_employee_id",
            "ambulance_vehicle_number",
            "is_verified",
            "date_joined",
        )
        read_only_fields = (
            "id",
            "username",
            "role",
            "is_verified",
            "date_joined",
            "ambulance_vehicle_number",
        )
