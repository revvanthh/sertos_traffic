"""
Automated Serializer Tests for SERTOS Authentication System (Step 3.4).

Verifies:
1. Valid ambulance driver registration.
2. Attempted ADMIN role escalation ignored/blocked on registration.
3. Attempted is_verified=True escalation ignored/blocked on registration.
4. Password hashing via set_password().
5. Password field is write-only and omitted from serialized output.
6. Weak/invalid password rejection by Django validators.
7. Duplicate username rejection.
8. JWT role and verification claims for an eligible verified user.
9. Rejection of unverified user from obtaining JWT tokens.
10. Profile serializer immutability of role and is_verified fields.
"""

from django.test import TestCase
from django.urls import resolve, reverse
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.exceptions import AuthenticationFailed
from rest_framework_simplejwt.tokens import UntypedToken

from apps.accounts.models import UserRole
from apps.emergencies.models import Ambulance
from apps.accounts.serializers import (
    CustomTokenObtainPairSerializer,
    UserRegistrationSerializer,
    UserProfileSerializer,
)

User = get_user_model()


class AccountsSerializerTestCase(TestCase):
    def setUp(self):
        # Create a verified test user for token validation tests
        self.verified_driver = User.objects.create_user(
            username="verified_driver",
            password="StrongPassword123!@#",
            email="driver@sertos.local",
            role=UserRole.AMBULANCE_DRIVER,
            is_verified=True,
            phone_number="+91-9876543210",
            badge_or_employee_id="AMB-001",
        )

        # Create an unverified test user
        self.unverified_driver = User.objects.create_user(
            username="unverified_driver",
            password="StrongPassword123!@#",
            email="unverified@sertos.local",
            role=UserRole.AMBULANCE_DRIVER,
            is_verified=False,
            phone_number="+91-9876543211",
            badge_or_employee_id="AMB-002",
        )

    def test_01_valid_ambulance_driver_registration(self):
        """1. Verify valid ambulance driver registration creates an unverified driver."""
        data = {
            "username": "new_driver",
            "password": "StrongPassword123!@#",
            "email": "new_driver@sertos.local",
            "phone_number": "+91-9876543212",
            "badge_or_employee_id": "AMB-003",
        }
        serializer = UserRegistrationSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        user = serializer.save()

        self.assertEqual(user.username, "new_driver")
        self.assertEqual(user.role, UserRole.AMBULANCE_DRIVER)
        self.assertFalse(user.is_verified)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_02_registration_attempted_admin_escalation_ignored(self):
        """2. Verify client-supplied role='ADMIN' is completely ignored."""
        data = {
            "username": "escalation_tester",
            "password": "StrongPassword123!@#",
            "email": "escalation@sertos.local",
            "role": "ADMIN",  # Attempted escalation
        }
        serializer = UserRegistrationSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        user = serializer.save()

        # Role must remain AMBULANCE_DRIVER
        self.assertEqual(user.role, UserRole.AMBULANCE_DRIVER)
        self.assertNotEqual(user.role, UserRole.ADMIN)

    def test_03_registration_attempted_is_verified_true_ignored(self):
        """3. Verify client-supplied is_verified=True is completely ignored."""
        data = {
            "username": "auto_verify_tester",
            "password": "StrongPassword123!@#",
            "email": "autoverify@sertos.local",
            "is_verified": True,  # Attempted auto-verification
        }
        serializer = UserRegistrationSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        user = serializer.save()

        # Must strictly remain False
        self.assertFalse(user.is_verified)

    def test_04_password_hashing(self):
        """4. Verify raw password is never stored and password is properly hashed."""
        raw_password = "StrongPassword123!@#"
        data = {
            "username": "hashing_tester",
            "password": raw_password,
            "email": "hashing@sertos.local",
        }
        serializer = UserRegistrationSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        user = serializer.save()

        # Raw password must not be stored
        self.assertNotEqual(user.password, raw_password)
        # Check password hash verification
        self.assertTrue(user.check_password(raw_password))

    def test_05_password_not_returned_in_serialized_output(self):
        """5. Verify password is write-only and not present in serializer.data."""
        data = {
            "username": "output_tester",
            "password": "StrongPassword123!@#",
            "email": "output@sertos.local",
        }
        serializer = UserRegistrationSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serialized_output = serializer.data

        self.assertNotIn("password", serialized_output)
        self.assertEqual(serialized_output["username"], "output_tester")

    def test_06_invalid_password_rejection(self):
        """6. Verify weak/short passwords are rejected by Django validators."""
        weak_data = {
            "username": "weak_tester",
            "password": "123",  # Too short and common
            "email": "weak@sertos.local",
        }
        serializer = UserRegistrationSerializer(data=weak_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("password", serializer.errors)

    def test_07_duplicate_username_rejection(self):
        """7. Verify registering an existing username raises validation error."""
        duplicate_data = {
            "username": "verified_driver",  # Already exists in setUp
            "password": "StrongPassword123!@#",
            "email": "duplicate@sertos.local",
        }
        serializer = UserRegistrationSerializer(data=duplicate_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("username", serializer.errors)

    def test_08_jwt_claims_for_verified_user(self):
        """8. Verify CustomTokenObtainPairSerializer adds user_id, role, is_verified claims."""
        data = {
            "username": "verified_driver",
            "password": "StrongPassword123!@#",
        }
        serializer = CustomTokenObtainPairSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        validated_data = serializer.validated_data

        self.assertIn("access", validated_data)
        self.assertIn("refresh", validated_data)
        self.assertIn("user", validated_data)

        # Decode access token to inspect custom claims
        decoded_access = UntypedToken(validated_data["access"])
        self.assertEqual(decoded_access["user_id"], self.verified_driver.id)
        self.assertEqual(decoded_access["role"], UserRole.AMBULANCE_DRIVER)
        self.assertTrue(decoded_access["is_verified"])

        # Sensitive info must NOT be in token
        self.assertNotIn("password", decoded_access)
        self.assertNotIn("phone_number", decoded_access)

    def test_09_unverified_user_cannot_obtain_tokens(self):
        """9. Verify unverified accounts cannot obtain tokens and trigger AuthenticationFailed."""
        data = {
            "username": "unverified_driver",
            "password": "StrongPassword123!@#",
        }
        serializer = CustomTokenObtainPairSerializer(data=data)
        with self.assertRaises(AuthenticationFailed) as context:
            serializer.is_valid(raise_exception=True)

        self.assertIn("pending administrative verification", str(context.exception))

    def test_10_profile_cannot_change_role_or_verification_status(self):
        """10. Verify UserProfileSerializer prevents updating role and is_verified."""
        serializer = UserProfileSerializer(
            instance=self.verified_driver,
            data={
                "phone_number": "+91-1122334455",
                "role": UserRole.ADMIN,  # Tampering attempt
                "is_verified": False,     # Tampering attempt
                "username": "tampered_name", # Tampering attempt
            },
            partial=True,
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        updated_user = serializer.save()

        # Phone number allowed to update
        self.assertEqual(updated_user.phone_number, "+91-1122334455")
        # Role, is_verified, and username must remain unchanged
        self.assertEqual(updated_user.role, UserRole.AMBULANCE_DRIVER)
        self.assertTrue(updated_user.is_verified)
        self.assertEqual(updated_user.username, "verified_driver")



from django.contrib.auth.models import AnonymousUser
from rest_framework.test import APIRequestFactory
from apps.accounts.permissions import (
    IsSystemAdmin,
    IsAmbulanceDriver,
    IsHospitalStaff,
    IsPoliceDispatcher,
    IsVerifiedPersonnel,
)


class AccountsPermissionsTestCase(TestCase):
    """
    Test suite for SERTOS Role-Based Access Control (RBAC) Permissions (Step 3.5).
    """

    def setUp(self):
        self.factory = APIRequestFactory()

        # Create verified users for all 4 operational roles
        self.admin_user = User.objects.create_user(
            username="admin_perm",
            password="StrongPassword123!@#",
            role=UserRole.ADMIN,
            is_verified=True,
        )
        self.driver_user = User.objects.create_user(
            username="driver_perm",
            password="StrongPassword123!@#",
            role=UserRole.AMBULANCE_DRIVER,
            is_verified=True,
        )
        self.hospital_user = User.objects.create_user(
            username="hospital_perm",
            password="StrongPassword123!@#",
            role=UserRole.HOSPITAL_STAFF,
            is_verified=True,
        )
        self.police_user = User.objects.create_user(
            username="police_perm",
            password="StrongPassword123!@#",
            role=UserRole.POLICE_DISPATCHER,
            is_verified=True,
        )

        # Create unverified counterparts
        self.unverified_admin = User.objects.create_user(
            username="unverified_admin_perm",
            password="StrongPassword123!@#",
            role=UserRole.ADMIN,
            is_verified=False,
        )
        self.unverified_driver = User.objects.create_user(
            username="unverified_driver_perm",
            password="StrongPassword123!@#",
            role=UserRole.AMBULANCE_DRIVER,
            is_verified=False,
        )

        # Instantiate permission classes
        self.perm_admin = IsSystemAdmin()
        self.perm_driver = IsAmbulanceDriver()
        self.perm_hospital = IsHospitalStaff()
        self.perm_police = IsPoliceDispatcher()
        self.perm_verified = IsVerifiedPersonnel()

    def _build_request(self, user):
        request = self.factory.get("/api/test-endpoint/")
        request.user = user
        return request

    def test_11_anonymous_user_denied_by_all_permissions(self):
        """1. Verify unauthenticated anonymous user is denied by every permission class."""
        request = self._build_request(AnonymousUser())
        self.assertFalse(self.perm_admin.has_permission(request, None))
        self.assertFalse(self.perm_driver.has_permission(request, None))
        self.assertFalse(self.perm_hospital.has_permission(request, None))
        self.assertFalse(self.perm_police.has_permission(request, None))
        self.assertFalse(self.perm_verified.has_permission(request, None))

    def test_12_correct_role_and_verified_user_allowed(self):
        """2. Verify each verified role passes its own permission check."""
        # Admin
        req_admin = self._build_request(self.admin_user)
        self.assertTrue(self.perm_admin.has_permission(req_admin, None))
        self.assertTrue(self.perm_verified.has_permission(req_admin, None))

        # Driver
        req_driver = self._build_request(self.driver_user)
        self.assertTrue(self.perm_driver.has_permission(req_driver, None))
        self.assertTrue(self.perm_verified.has_permission(req_driver, None))

        # Hospital Staff
        req_hospital = self._build_request(self.hospital_user)
        self.assertTrue(self.perm_hospital.has_permission(req_hospital, None))
        self.assertTrue(self.perm_verified.has_permission(req_hospital, None))

        # Police Dispatcher
        req_police = self._build_request(self.police_user)
        self.assertTrue(self.perm_police.has_permission(req_police, None))
        self.assertTrue(self.perm_verified.has_permission(req_police, None))

    def test_13_incorrect_role_denied(self):
        """3. Verify users are denied access to roles other than their own."""
        req_driver = self._build_request(self.driver_user)
        self.assertFalse(self.perm_admin.has_permission(req_driver, None))
        self.assertFalse(self.perm_hospital.has_permission(req_driver, None))
        self.assertFalse(self.perm_police.has_permission(req_driver, None))

        req_hospital = self._build_request(self.hospital_user)
        self.assertFalse(self.perm_admin.has_permission(req_hospital, None))
        self.assertFalse(self.perm_driver.has_permission(req_hospital, None))
        self.assertFalse(self.perm_police.has_permission(req_hospital, None))

    def test_14_unverified_user_denied(self):
        """4. Verify unverified users are denied across all permission classes."""
        req_unverified_admin = self._build_request(self.unverified_admin)
        self.assertFalse(self.perm_admin.has_permission(req_unverified_admin, None))
        self.assertFalse(self.perm_verified.has_permission(req_unverified_admin, None))

        req_unverified_driver = self._build_request(self.unverified_driver)
        self.assertFalse(self.perm_driver.has_permission(req_unverified_driver, None))
        self.assertFalse(self.perm_verified.has_permission(req_unverified_driver, None))

    def test_15_database_role_checked_rather_than_payload(self):
        """5. Verify permissions evaluate the database model rather than arbitrary request attributes."""
        # Simulated user with driver in database
        req = self._build_request(self.driver_user)
        # Attempt to inject simulated fabricated role in request payload or query
        req.data = {"role": "ADMIN"}
        req.META["HTTP_X_ROLE_OVERRIDE"] = "ADMIN"

        # Permission must still strictly deny Admin and grant Driver
        self.assertFalse(self.perm_admin.has_permission(req, None))
        self.assertTrue(self.perm_driver.has_permission(req, None))

    def test_16_verification_revocation_in_database_respected(self):
        """6. Verify revoking is_verified in the database immediately revokes permissions."""
        driver = User.objects.create_user(
            username="revocation_driver",
            password="StrongPassword123!@#",
            role=UserRole.AMBULANCE_DRIVER,
            is_verified=True,
        )
        req = self._build_request(driver)
        self.assertTrue(self.perm_driver.has_permission(req, None))
        self.assertTrue(self.perm_verified.has_permission(req, None))

        # Administrator revokes verification in database
        driver.is_verified = False
        driver.save()
        driver.refresh_from_db()

        # On next request, permission check fails immediately
        req_after = self._build_request(driver)
        self.assertFalse(self.perm_driver.has_permission(req_after, None))
        self.assertFalse(self.perm_verified.has_permission(req_after, None))

    def test_17_all_four_roles_correctly_distinguished(self):
        """7. Verify each of the 4 operational roles is uniquely distinguished with zero collision."""
        roles_and_users = [
            (UserRole.ADMIN, self.admin_user, self.perm_admin),
            (UserRole.AMBULANCE_DRIVER, self.driver_user, self.perm_driver),
            (UserRole.HOSPITAL_STAFF, self.hospital_user, self.perm_hospital),
            (UserRole.POLICE_DISPATCHER, self.police_user, self.perm_police),
        ]

        for target_role, user, permission in roles_and_users:
            req = self._build_request(user)
            # Only the matching permission must succeed
            for other_role, other_user, other_permission in roles_and_users:
                if other_permission == permission:
                    self.assertTrue(
                        other_permission.has_permission(req, None),
                        f"User with role {target_role} failed its own permission check.",
                    )
                else:
                    self.assertFalse(
                        other_permission.has_permission(req, None),
                        f"User with role {target_role} improperly allowed access to {other_role} permission.",
                    )



from rest_framework.test import force_authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from apps.accounts.views import (
    LoginView,
    TokenRefreshView,
    LogoutView,
    RegisterView,
    ProfileView,
)


class AccountsViewsTestCase(TestCase):
    """
    Test suite for SERTOS Authentication and Profile API Views (Step 3.6).
    """

    def setUp(self):
        self.factory = APIRequestFactory()

        # Verified driver
        self.verified_driver = User.objects.create_user(
            username="view_verified_driver",
            password="StrongPassword123!@#",
            email="verified_driver@sertos.local",
            role=UserRole.AMBULANCE_DRIVER,
            is_verified=True,
            phone_number="+91-9876543210",
            badge_or_employee_id="AMB-V01",
        )

        # Unverified driver
        self.unverified_driver = User.objects.create_user(
            username="view_unverified_driver",
            password="StrongPassword123!@#",
            email="unverified_driver@sertos.local",
            role=UserRole.AMBULANCE_DRIVER,
            is_verified=False,
            phone_number="+91-9876543211",
            badge_or_employee_id="AMB-V02",
        )

        # Second verified user (for token cross-ownership tests)
        self.other_user = User.objects.create_user(
            username="view_other_user",
            password="StrongPassword123!@#",
            email="other@sertos.local",
            role=UserRole.HOSPITAL_STAFF,
            is_verified=True,
        )

        # Inactive driver (for inactive login rejection tests)
        self.inactive_driver = User.objects.create_user(
            username="view_inactive_driver",
            password="StrongPassword123!@#",
            email="inactive_driver@sertos.local",
            role=UserRole.AMBULANCE_DRIVER,
            is_verified=True,
            is_active=False,
        )

    def test_18_valid_login(self):
        """1. Verify valid login returns 200, JWT tokens, user metadata, and standard envelope."""
        request = self.factory.post(
            "/api/auth/login/",
            {
                "username": "view_verified_driver",
                "password": "StrongPassword123!@#",
            },
            format="json",
        )
        response = LoginView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        self.assertIn("access", response.data["data"])
        self.assertIn("refresh", response.data["data"])
        self.assertIn("user", response.data["data"])
        self.assertIn("timestamp", response.data)
        self.assertEqual(response.data["data"]["user"]["username"], "view_verified_driver")

    def test_19_invalid_login(self):
        """2. Verify login with wrong password returns 401 with standard error envelope."""
        request = self.factory.post(
            "/api/auth/login/",
            {
                "username": "view_verified_driver",
                "password": "WrongPassword999!",
            },
            format="json",
        )
        response = LoginView.as_view()(request)

        self.assertEqual(response.status_code, 401)
        self.assertFalse(response.data["success"])
        self.assertIn("errors", response.data)
        self.assertNotIn("access", response.data["data"])

    def test_20_unverified_login_rejection(self):
        """3. Verify login for an unverified account returns 401 and rejects token issuance."""
        request = self.factory.post(
            "/api/auth/login/",
            {
                "username": "view_unverified_driver",
                "password": "StrongPassword123!@#",
            },
            format="json",
        )
        response = LoginView.as_view()(request)

        self.assertEqual(response.status_code, 401)
        self.assertFalse(response.data["success"])
        self.assertIn("errors", response.data)
        self.assertIn("administrative verification", response.data["message"])

    def test_20a_missing_username_returns_400(self):
        """3a. Verify login missing username returns 400 with 'Invalid request data.'."""
        request = self.factory.post(
            "/api/auth/login/",
            {"password": "StrongPassword123!@#"},
            format="json",
        )
        response = LoginView.as_view()(request)

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data["success"])
        self.assertEqual(response.data["message"], "Invalid request data.")
        self.assertIn("username", response.data["errors"])

    def test_20b_missing_password_returns_400(self):
        """3b. Verify login missing password returns 400 with 'Invalid request data.'."""
        request = self.factory.post(
            "/api/auth/login/",
            {"username": "view_verified_driver"},
            format="json",
        )
        response = LoginView.as_view()(request)

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data["success"])
        self.assertEqual(response.data["message"], "Invalid request data.")
        self.assertIn("password", response.data["errors"])

    def test_20c_inactive_user_login_rejection(self):
        """3c. Verify login for an inactive account returns 401 and rejects token issuance."""
        request = self.factory.post(
            "/api/auth/login/",
            {
                "username": "view_inactive_driver",
                "password": "StrongPassword123!@#",
            },
            format="json",
        )
        response = LoginView.as_view()(request)

        self.assertEqual(response.status_code, 401)
        self.assertFalse(response.data["success"])
        self.assertIn("errors", response.data)

    def test_21_valid_token_refresh(self):
        """4. Verify refreshing with a valid refresh token returns 200 and a new access token."""
        refresh = RefreshToken.for_user(self.verified_driver)
        request = self.factory.post(
            "/api/auth/token/refresh/",
            {"refresh": str(refresh)},
            format="json",
        )
        response = TokenRefreshView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        self.assertIn("access", response.data["data"])

    def test_22_invalid_refresh_token_rejection(self):
        """5. Verify invalid or tampered refresh token returns 401."""
        request = self.factory.post(
            "/api/auth/token/refresh/",
            {"refresh": "malformed.or.invalid.token"},
            format="json",
        )
        response = TokenRefreshView.as_view()(request)

        self.assertEqual(response.status_code, 401)
        self.assertFalse(response.data["success"])

    def test_23_successful_logout(self):
        """6. Verify authenticated user can logout and blacklist their own refresh token."""
        refresh = RefreshToken.for_user(self.verified_driver)
        request = self.factory.post(
            "/api/auth/logout/",
            {"refresh": str(refresh)},
            format="json",
        )
        force_authenticate(request, user=self.verified_driver)
        response = LogoutView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        self.assertIn("invalidated", response.data["message"])

    def test_24_reuse_of_blacklisted_refresh_token_fails(self):
        """7. Verify refresh token that has been blacklisted via logout cannot be used to refresh."""
        refresh = RefreshToken.for_user(self.verified_driver)
        logout_request = self.factory.post(
            "/api/auth/logout/",
            {"refresh": str(refresh)},
            format="json",
        )
        force_authenticate(logout_request, user=self.verified_driver)
        logout_response = LogoutView.as_view()(logout_request)
        self.assertEqual(logout_response.status_code, 200)

        # Attempt to refresh using the blacklisted token
        refresh_request = self.factory.post(
            "/api/auth/token/refresh/",
            {"refresh": str(refresh)},
            format="json",
        )
        refresh_response = TokenRefreshView.as_view()(refresh_request)
        self.assertEqual(refresh_response.status_code, 401)
        self.assertFalse(refresh_response.data["success"])

    def test_25_logout_using_another_users_token_rejected(self):
        """8. Verify submitting another user's refresh token on logout returns 403 Forbidden."""
        # Generate token for other_user
        token_for_other = RefreshToken.for_user(self.other_user)

        # verified_driver tries to submit other_user's token
        request = self.factory.post(
            "/api/auth/logout/",
            {"refresh": str(token_for_other)},
            format="json",
        )
        force_authenticate(request, user=self.verified_driver)
        response = LogoutView.as_view()(request)

        self.assertEqual(response.status_code, 403)
        self.assertFalse(response.data["success"])
        self.assertIn("Forbidden", response.data["message"])

    def test_26_successful_driver_registration(self):
        """9. Verify driver self-registration returns 201 Created and unverified status."""
        request = self.factory.post(
            "/api/auth/register/",
            {
                "username": "api_new_driver",
                "password": "StrongPassword123!@#",
                "email": "api_driver@sertos.local",
                "phone_number": "+91-9876543299",
                "badge_or_employee_id": "AMB-V99",
            },
            format="json",
        )
        response = RegisterView.as_view()(request)

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["data"]["username"], "api_new_driver")
        self.assertEqual(response.data["data"]["role"], UserRole.AMBULANCE_DRIVER)
        self.assertFalse(response.data["data"]["is_verified"])
        self.assertNotIn("password", response.data["data"])

    def test_27_privilege_escalation_during_registration_prevented(self):
        """10. Verify attempted ADMIN or is_verified injection on registration is prevented."""
        request = self.factory.post(
            "/api/auth/register/",
            {
                "username": "api_hacker",
                "password": "StrongPassword123!@#",
                "email": "hacker@sertos.local",
                "role": "ADMIN",
                "is_verified": True,
            },
            format="json",
        )
        response = RegisterView.as_view()(request)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["data"]["role"], UserRole.AMBULANCE_DRIVER)
        self.assertFalse(response.data["data"]["is_verified"])

    def test_28_anonymous_profile_access_rejected(self):
        """11. Verify unauthenticated profile request returns 401 Unauthorized."""
        request = self.factory.get("/api/auth/profile/")
        response = ProfileView.as_view()(request)

        self.assertEqual(response.status_code, 401)

    def test_29_authenticated_profile_retrieval(self):
        """12. Verify authenticated user can retrieve their own profile with envelope."""
        Ambulance.objects.create(
            vehicle_number="TEST-PROFILE-AMB",
            vehicle_type="Advanced Life Support",
            assigned_driver=self.verified_driver,
        )
        request = self.factory.get("/api/auth/profile/")
        force_authenticate(request, user=self.verified_driver)
        response = ProfileView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["data"]["username"], "view_verified_driver")
        self.assertEqual(response.data["data"]["role"], UserRole.AMBULANCE_DRIVER)
        self.assertEqual(response.data["data"]["ambulance_vehicle_number"], "TEST-PROFILE-AMB")
        self.assertNotIn("password", response.data["data"])

    def test_30_profile_update_cannot_change_role_or_verification(self):
        """13. Verify PATCH to profile updates phone, but ignores role or is_verified changes."""
        request = self.factory.patch(
            "/api/auth/profile/",
            {
                "phone_number": "+91-9988776655",
                "role": UserRole.ADMIN,
                "is_verified": False,
            },
            format="json",
        )
        force_authenticate(request, user=self.verified_driver)
        response = ProfileView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["data"]["phone_number"], "+91-9988776655")
        self.assertEqual(response.data["data"]["role"], UserRole.AMBULANCE_DRIVER)
        self.assertTrue(response.data["data"]["is_verified"])

    def test_31_standard_response_envelope_structure(self):
        """14. Verify standard response envelope structure across success and error responses."""
        request = self.factory.get("/api/auth/profile/")
        force_authenticate(request, user=self.verified_driver)
        response = ProfileView.as_view()(request)

        self.assertIn("success", response.data)
        self.assertIn("data", response.data)
        self.assertIn("message", response.data)
        self.assertIn("timestamp", response.data)


class AccountsRoutingAndIntegrationTestCase(TestCase):
    """
    Integration and URL Routing Test Suite for SERTOS Authentication Subsystem (Step 3.7).

    Validates:
    1. All 5 URL paths resolve to the correct DRF class-based views.
    2. /api/auth/login/ accepts unauthenticated requests.
    3. /api/auth/register/ accepts unauthenticated requests.
    4. /api/auth/token/refresh/ accepts unauthenticated requests with a valid refresh token.
    5. /api/auth/logout/ rejects unauthenticated requests (HTTP 401).
    6. /api/auth/profile/ rejects unauthenticated requests (HTTP 401).
    7. A verified user can log in and retrieve their profile through the routed URLs.
    8. Registration through the routed URL creates an unverified ambulance driver.
    9. The standard response envelope is preserved across routed endpoints.
    10. A user whose verification is revoked cannot use an old refresh token to obtain another access token.
    11. A deactivated user cannot use an old refresh token to obtain another access token.
    """

    def setUp(self):
        self.client = APIClient()

        # Verified driver for login and profile tests
        self.verified_driver = User.objects.create_user(
            username="routed_verified_driver",
            password="StrongPassword123!@#",
            email="routed_driver@sertos.local",
            role=UserRole.AMBULANCE_DRIVER,
            is_verified=True,
            phone_number="+91-9123456780",
            badge_or_employee_id="AMB-R01",
        )

        # Unverified driver
        self.unverified_driver = User.objects.create_user(
            username="routed_unverified_driver",
            password="StrongPassword123!@#",
            email="routed_unverified@sertos.local",
            role=UserRole.AMBULANCE_DRIVER,
            is_verified=False,
            phone_number="+91-9123456781",
            badge_or_employee_id="AMB-R02",
        )

    def test_32_url_paths_resolve_to_correct_views(self):
        """1. Verify all five URL paths resolve to the correct views and reverse names."""
        routes = [
            ("/api/auth/login/", LoginView, "login"),
            ("/api/auth/token/refresh/", TokenRefreshView, "token_refresh"),
            ("/api/auth/logout/", LogoutView, "logout"),
            ("/api/auth/register/", RegisterView, "register"),
            ("/api/auth/profile/", ProfileView, "profile"),
        ]

        for path_str, view_cls, route_name in routes:
            resolver = resolve(path_str)
            self.assertEqual(
                resolver.func.view_class,
                view_cls,
                f"Path {path_str} did not resolve to {view_cls.__name__}.",
            )
            self.assertEqual(
                resolver.url_name,
                route_name,
                f"Path {path_str} url_name is '{resolver.url_name}', expected '{route_name}'.",
            )
            self.assertEqual(reverse(route_name), path_str)

    def test_33_login_endpoint_accepts_unauthenticated_request(self):
        """2. Verify login endpoint accepts an unauthenticated request."""
        response = self.client.post(
            "/api/auth/login/",
            {
                "username": "routed_verified_driver",
                "password": "StrongPassword123!@#",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        self.assertIn("access", response.data["data"])
        self.assertIn("refresh", response.data["data"])

    def test_34_registration_endpoint_accepts_unauthenticated_request(self):
        """3. Verify registration endpoint accepts an unauthenticated request."""
        response = self.client.post(
            "/api/auth/register/",
            {
                "username": "routed_new_driver",
                "email": "routed_new@sertos.local",
                "password": "StrongPassword123!@#",
                "phone_number": "+91-9876543299",
                "badge_or_employee_id": "AMB-R99",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["data"]["username"], "routed_new_driver")

    def test_35_token_refresh_accepts_unauthenticated_request_with_valid_token(self):
        """4. Verify token refresh endpoint accepts an unauthenticated request with a valid refresh token."""
        login_res = self.client.post(
            "/api/auth/login/",
            {
                "username": "routed_verified_driver",
                "password": "StrongPassword123!@#",
            },
            format="json",
        )
        refresh_token = login_res.data["data"]["refresh"]

        response = self.client.post(
            "/api/auth/token/refresh/",
            {"refresh": refresh_token},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        self.assertIn("access", response.data["data"])
        self.assertEqual(response.data["message"], "Access token refreshed successfully.")

    def test_36_logout_endpoint_rejects_unauthenticated_requests(self):
        """5. Verify logout endpoint rejects unauthenticated requests with HTTP 401."""
        response = self.client.post(
            "/api/auth/logout/",
            {"refresh": "any_token"},
            format="json",
        )
        self.assertEqual(response.status_code, 401)

    def test_37_profile_endpoint_rejects_unauthenticated_requests(self):
        """6. Verify profile endpoint rejects unauthenticated requests with HTTP 401."""
        response = self.client.get("/api/auth/profile/")
        self.assertEqual(response.status_code, 401)

    def test_38_verified_user_login_and_retrieve_profile_via_routed_urls(self):
        """7. Verify a verified user can log in and retrieve their profile through the routed URLs."""
        login_res = self.client.post(
            "/api/auth/login/",
            {
                "username": "routed_verified_driver",
                "password": "StrongPassword123!@#",
            },
            format="json",
        )
        self.assertEqual(login_res.status_code, 200)
        access_token = login_res.data["data"]["access"]

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        profile_res = self.client.get("/api/auth/profile/")

        self.assertEqual(profile_res.status_code, 200)
        self.assertTrue(profile_res.data["success"])
        self.assertEqual(profile_res.data["data"]["username"], "routed_verified_driver")
        self.assertEqual(profile_res.data["data"]["role"], UserRole.AMBULANCE_DRIVER)
        self.assertTrue(profile_res.data["data"]["is_verified"])
        self.assertEqual(profile_res.data["data"]["badge_or_employee_id"], "AMB-R01")

    def test_39_registration_through_routed_url_creates_unverified_driver(self):
        """8. Verify registration through the routed URL creates an unverified ambulance driver."""
        response = self.client.post(
            "/api/auth/register/",
            {
                "username": "driver_via_route",
                "email": "driver_route@sertos.local",
                "password": "StrongPassword123!@#",
                "phone_number": "+91-9123499999",
                "badge_or_employee_id": "AMB-R88",
                "role": "ADMIN",
                "is_verified": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)

        created_user = User.objects.get(username="driver_via_route")
        self.assertEqual(created_user.role, UserRole.AMBULANCE_DRIVER)
        self.assertFalse(created_user.is_verified)
        self.assertFalse(created_user.is_staff)
        self.assertFalse(created_user.is_superuser)

    def test_40_standard_response_envelope_preserved_across_routed_endpoints(self):
        """9. Verify the standard response envelope is preserved through routed endpoints."""
        login_res = self.client.post(
            "/api/auth/login/",
            {
                "username": "routed_verified_driver",
                "password": "StrongPassword123!@#",
            },
            format="json",
        )
        for key in ("success", "data", "message", "timestamp"):
            self.assertIn(key, login_res.data)
        self.assertTrue(login_res.data["success"])

        bad_login_res = self.client.post(
            "/api/auth/login/",
            {
                "username": "routed_verified_driver",
                "password": "WrongPassword999!",
            },
            format="json",
        )
        for key in ("success", "data", "message", "timestamp", "errors"):
            self.assertIn(key, bad_login_res.data)
        self.assertFalse(bad_login_res.data["success"])

        unverified_login_res = self.client.post(
            "/api/auth/login/",
            {
                "username": "routed_unverified_driver",
                "password": "StrongPassword123!@#",
            },
            format="json",
        )
        self.assertEqual(unverified_login_res.status_code, 401)
        self.assertFalse(unverified_login_res.data["success"])
        self.assertIn("errors", unverified_login_res.data)

    def test_41_user_verification_revoked_cannot_use_old_refresh_token(self):
        """10. Verify a user whose verification is revoked in DB cannot use an old refresh token to obtain access token."""
        login_res = self.client.post(
            "/api/auth/login/",
            {
                "username": "routed_verified_driver",
                "password": "StrongPassword123!@#",
            },
            format="json",
        )
        self.assertEqual(login_res.status_code, 200)
        refresh_token = login_res.data["data"]["refresh"]

        # Revoke verification in PostgreSQL database
        self.verified_driver.is_verified = False
        self.verified_driver.save()

        # Attempt to use old refresh token
        refresh_res = self.client.post(
            "/api/auth/token/refresh/",
            {"refresh": refresh_token},
            format="json",
        )

        self.assertEqual(refresh_res.status_code, 401)
        self.assertFalse(refresh_res.data["success"])
        self.assertIn("errors", refresh_res.data)
        self.assertIn("Account verification has been revoked", refresh_res.data["message"])

    def test_42_deactivated_user_cannot_use_old_refresh_token(self):
        """11. Verify a user whose account is deactivated cannot use an old refresh token."""
        active_user = User.objects.create_user(
            username="active_to_deactivate",
            password="StrongPassword123!@#",
            role=UserRole.HOSPITAL_STAFF,
            is_verified=True,
        )
        login_res = self.client.post(
            "/api/auth/login/",
            {
                "username": "active_to_deactivate",
                "password": "StrongPassword123!@#",
            },
            format="json",
        )
        self.assertEqual(login_res.status_code, 200)
        refresh_token = login_res.data["data"]["refresh"]

        active_user.is_active = False
        active_user.save()

        refresh_res = self.client.post(
            "/api/auth/token/refresh/",
            {"refresh": refresh_token},
            format="json",
        )
        self.assertEqual(refresh_res.status_code, 401)
        self.assertFalse(refresh_res.data["success"])


from rest_framework.views import APIView
from rest_framework.response import Response


# Test-only class-based views for strict isolated permission testing (not exposed to production)
class _TestHospitalOnlyView(APIView):
    permission_classes = [IsHospitalStaff]

    def get(self, request):
        return Response({"status": "hospital_granted"})


class _TestPoliceOnlyView(APIView):
    permission_classes = [IsPoliceDispatcher]

    def get(self, request):
        return Response({"status": "police_granted"})


class _TestAdminOnlyView(APIView):
    permission_classes = [IsSystemAdmin]

    def get(self, request):
        return Response({"status": "admin_granted"})


class AccountsEndToEndValidationTestCase(TestCase):
    """
    Step 3.8: Comprehensive End-to-End Authentication and RBAC Validation Test Suite.

    Validates:
    TEST-43: End-to-End Login & Profile Retrieval for ADMIN.
    TEST-44: End-to-End Login & Profile Retrieval for HOSPITAL_STAFF.
    TEST-45: End-to-End Login & Profile Retrieval for POLICE_DISPATCHER.
    TEST-46: Cross-Role Endpoint Authorization Gating (Ambulance Driver accessing Hospital view).
    TEST-47: Cross-Role Endpoint Authorization Gating (Hospital Staff accessing Police view).
    TEST-48: Cross-Role Endpoint Authorization Gating (Police Dispatcher accessing Admin view).
    TEST-49: Token Rotation Replay Attack Prevention (Reusing old rotated refresh token).
    TEST-50: Concurrent Multi-Device Session Isolation (Device 1 logout leaves Device 2 active).
    TEST-51: Malformed and Tampered Bearer Token Gating (Corrupted, non-JWT, non-Bearer headers).
    TEST-52: Empty and Malformed Request Payload Handling (Boundary tests across all auth endpoints).
    """

    def setUp(self):
        self.client = APIClient()
        self.factory = APIRequestFactory()

        # Create isolated users for all 4 roles
        self.admin_user = User.objects.create_user(
            username="e2e_admin",
            password="StrongPassword123!@#",
            email="admin@sertos.local",
            role=UserRole.ADMIN,
            is_verified=True,
            phone_number="+91-9000000001",
            badge_or_employee_id="ADM-001",
        )

        self.driver_user = User.objects.create_user(
            username="e2e_driver",
            password="StrongPassword123!@#",
            email="driver@sertos.local",
            role=UserRole.AMBULANCE_DRIVER,
            is_verified=True,
            phone_number="+91-9000000002",
            badge_or_employee_id="AMB-002",
        )

        self.hospital_user = User.objects.create_user(
            username="e2e_hospital",
            password="StrongPassword123!@#",
            email="hospital@sertos.local",
            role=UserRole.HOSPITAL_STAFF,
            is_verified=True,
            phone_number="+91-9000000003",
            badge_or_employee_id="HOS-003",
        )

        self.police_user = User.objects.create_user(
            username="e2e_police",
            password="StrongPassword123!@#",
            email="police@sertos.local",
            role=UserRole.POLICE_DISPATCHER,
            is_verified=True,
            phone_number="+91-9000000004",
            badge_or_employee_id="POL-004",
        )

    def test_43_admin_login_and_profile_retrieval(self):
        """TEST-43: Verify ADMIN can log in, receive ADMIN JWT claims, and retrieve profile."""
        login_res = self.client.post(
            "/api/auth/login/",
            {
                "username": "e2e_admin",
                "password": "StrongPassword123!@#",
            },
            format="json",
        )
        self.assertEqual(login_res.status_code, 200)
        self.assertTrue(login_res.data["success"])
        self.assertEqual(login_res.data["data"]["user"]["role"], UserRole.ADMIN)

        access_token = login_res.data["data"]["access"]
        decoded_token = UntypedToken(access_token)
        self.assertEqual(decoded_token["role"], UserRole.ADMIN)
        self.assertTrue(decoded_token["is_verified"])

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        profile_res = self.client.get("/api/auth/profile/")
        self.assertEqual(profile_res.status_code, 200)
        self.assertTrue(profile_res.data["success"])
        self.assertEqual(profile_res.data["data"]["username"], "e2e_admin")
        self.assertEqual(profile_res.data["data"]["role"], UserRole.ADMIN)
        self.assertNotIn("password", profile_res.data["data"])

    def test_44_hospital_staff_login_and_profile_retrieval(self):
        """TEST-44: Verify HOSPITAL_STAFF can log in, receive hospital claims, and retrieve profile."""
        login_res = self.client.post(
            "/api/auth/login/",
            {
                "username": "e2e_hospital",
                "password": "StrongPassword123!@#",
            },
            format="json",
        )
        self.assertEqual(login_res.status_code, 200)
        self.assertTrue(login_res.data["success"])
        self.assertEqual(login_res.data["data"]["user"]["role"], UserRole.HOSPITAL_STAFF)

        access_token = login_res.data["data"]["access"]
        decoded_token = UntypedToken(access_token)
        self.assertEqual(decoded_token["role"], UserRole.HOSPITAL_STAFF)

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        profile_res = self.client.get("/api/auth/profile/")
        self.assertEqual(profile_res.status_code, 200)
        self.assertTrue(profile_res.data["success"])
        self.assertEqual(profile_res.data["data"]["username"], "e2e_hospital")
        self.assertEqual(profile_res.data["data"]["role"], UserRole.HOSPITAL_STAFF)
        self.assertNotIn("password", profile_res.data["data"])

    def test_45_police_dispatcher_login_and_profile_retrieval(self):
        """TEST-45: Verify POLICE_DISPATCHER can log in, receive police claims, and retrieve profile."""
        login_res = self.client.post(
            "/api/auth/login/",
            {
                "username": "e2e_police",
                "password": "StrongPassword123!@#",
            },
            format="json",
        )
        self.assertEqual(login_res.status_code, 200)
        self.assertTrue(login_res.data["success"])
        self.assertEqual(login_res.data["data"]["user"]["role"], UserRole.POLICE_DISPATCHER)

        access_token = login_res.data["data"]["access"]
        decoded_token = UntypedToken(access_token)
        self.assertEqual(decoded_token["role"], UserRole.POLICE_DISPATCHER)

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        profile_res = self.client.get("/api/auth/profile/")
        self.assertEqual(profile_res.status_code, 200)
        self.assertTrue(profile_res.data["success"])
        self.assertEqual(profile_res.data["data"]["username"], "e2e_police")
        self.assertEqual(profile_res.data["data"]["role"], UserRole.POLICE_DISPATCHER)
        self.assertNotIn("password", profile_res.data["data"])

    def test_46_ambulance_driver_denied_hospital_permission(self):
        """TEST-46: Verify ambulance driver accessing hospital-only view is denied with HTTP 403."""
        # 1. Direct permission check
        perm = IsHospitalStaff()
        req = self.factory.get("/test/hospital/")
        req.user = self.driver_user
        force_authenticate(req, user=self.driver_user)
        self.assertFalse(perm.has_permission(req, None))
        self.assertEqual(perm.message, "Access denied: Hospital Emergency Staff credentials required.")

        # 2. View execution check
        response = _TestHospitalOnlyView.as_view()(req)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["detail"], "Access denied: Hospital Emergency Staff credentials required.")

        # 3. Verify hospital staff is permitted
        req_allowed = self.factory.get("/test/hospital/")
        req_allowed.user = self.hospital_user
        force_authenticate(req_allowed, user=self.hospital_user)
        response_allowed = _TestHospitalOnlyView.as_view()(req_allowed)
        self.assertEqual(response_allowed.status_code, 200)
        self.assertEqual(response_allowed.data["status"], "hospital_granted")

    def test_47_hospital_staff_denied_police_permission(self):
        """TEST-47: Verify hospital staff accessing police-only view is denied with HTTP 403."""
        # 1. Direct permission check
        perm = IsPoliceDispatcher()
        req = self.factory.get("/test/police/")
        req.user = self.hospital_user
        force_authenticate(req, user=self.hospital_user)
        self.assertFalse(perm.has_permission(req, None))
        self.assertEqual(perm.message, "Access denied: Police Traffic Dispatcher credentials required.")

        # 2. View execution check
        response = _TestPoliceOnlyView.as_view()(req)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["detail"], "Access denied: Police Traffic Dispatcher credentials required.")

        # 3. Verify police dispatcher is permitted
        req_allowed = self.factory.get("/test/police/")
        req_allowed.user = self.police_user
        force_authenticate(req_allowed, user=self.police_user)
        response_allowed = _TestPoliceOnlyView.as_view()(req_allowed)
        self.assertEqual(response_allowed.status_code, 200)
        self.assertEqual(response_allowed.data["status"], "police_granted")

    def test_48_police_dispatcher_denied_admin_permission(self):
        """TEST-48: Verify police dispatcher accessing admin-only view is denied with HTTP 403."""
        # 1. Direct permission check
        perm = IsSystemAdmin()
        req = self.factory.get("/test/admin/")
        req.user = self.police_user
        force_authenticate(req, user=self.police_user)
        self.assertFalse(perm.has_permission(req, None))
        self.assertEqual(perm.message, "Access denied: System Administrator privileges required.")

        # 2. View execution check
        response = _TestAdminOnlyView.as_view()(req)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["detail"], "Access denied: System Administrator privileges required.")

        # 3. Verify admin is permitted
        req_allowed = self.factory.get("/test/admin/")
        req_allowed.user = self.admin_user
        force_authenticate(req_allowed, user=self.admin_user)
        response_allowed = _TestAdminOnlyView.as_view()(req_allowed)
        self.assertEqual(response_allowed.status_code, 200)
        self.assertEqual(response_allowed.data["status"], "admin_granted")

    def test_49_refresh_token_rotation_replay_prevention(self):
        """TEST-49: Verify that an old refresh token cannot be reused after token rotation."""
        login_res = self.client.post(
            "/api/auth/login/",
            {
                "username": "e2e_driver",
                "password": "StrongPassword123!@#",
            },
            format="json",
        )
        self.assertEqual(login_res.status_code, 200)
        original_refresh = login_res.data["data"]["refresh"]

        # First refresh: must succeed and rotate token
        first_refresh_res = self.client.post(
            "/api/auth/token/refresh/",
            {"refresh": original_refresh},
            format="json",
        )
        self.assertEqual(first_refresh_res.status_code, 200)
        self.assertTrue(first_refresh_res.data["success"])
        new_refresh = first_refresh_res.data["data"]["refresh"]
        self.assertNotEqual(original_refresh, new_refresh)

        # Replay attempt: submitting original_refresh again must fail
        replay_res = self.client.post(
            "/api/auth/token/refresh/",
            {"refresh": original_refresh},
            format="json",
        )
        self.assertEqual(replay_res.status_code, 401)
        self.assertFalse(replay_res.data["success"])
        self.assertIn("Token is blacklisted", str(replay_res.data))

        # Verify the new_refresh token remains fully valid and operational
        second_refresh_res = self.client.post(
            "/api/auth/token/refresh/",
            {"refresh": new_refresh},
            format="json",
        )
        self.assertEqual(second_refresh_res.status_code, 200)
        self.assertTrue(second_refresh_res.data["success"])

    def test_50_independent_multi_device_refresh_sessions(self):
        """TEST-50: Verify that logging out on Device 1 does not invalidate Device 2's refresh token."""
        # Device 1 login
        login_dev1 = self.client.post(
            "/api/auth/login/",
            {
                "username": "e2e_driver",
                "password": "StrongPassword123!@#",
            },
            format="json",
        )
        self.assertEqual(login_dev1.status_code, 200)
        refresh_dev1 = login_dev1.data["data"]["refresh"]
        access_dev1 = login_dev1.data["data"]["access"]

        # Device 2 login (same user, separate session)
        login_dev2 = self.client.post(
            "/api/auth/login/",
            {
                "username": "e2e_driver",
                "password": "StrongPassword123!@#",
            },
            format="json",
        )
        self.assertEqual(login_dev2.status_code, 200)
        refresh_dev2 = login_dev2.data["data"]["refresh"]
        self.assertNotEqual(refresh_dev1, refresh_dev2)

        # Device 1 logs out
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_dev1}")
        logout_res = self.client.post(
            "/api/auth/logout/",
            {"refresh": refresh_dev1},
            format="json",
        )
        self.assertEqual(logout_res.status_code, 200)
        self.assertTrue(logout_res.data["success"])

        # Device 1 refresh token is now dead
        dev1_refresh_retry = self.client.post(
            "/api/auth/token/refresh/",
            {"refresh": refresh_dev1},
            format="json",
        )
        self.assertEqual(dev1_refresh_retry.status_code, 401)

        # Clear credentials and verify Device 2 refresh token is STILL VALID
        self.client.credentials()
        dev2_refresh_res = self.client.post(
            "/api/auth/token/refresh/",
            {"refresh": refresh_dev2},
            format="json",
        )
        self.assertEqual(dev2_refresh_res.status_code, 200)
        self.assertTrue(dev2_refresh_res.data["success"])
        self.assertIn("access", dev2_refresh_res.data["data"])

    def test_51_malformed_and_tampered_bearer_tokens(self):
        """TEST-51: Verify malformed, tampered, or invalid Authorization headers are rejected with HTTP 401."""
        # 1. Completely bogus string
        self.client.credentials(HTTP_AUTHORIZATION="Bearer completely.bogus.jwt")
        res1 = self.client.get("/api/auth/profile/")
        self.assertEqual(res1.status_code, 401)
        self.assertNotIn("password", str(res1.data))

        # 2. Non-Bearer authorization scheme
        self.client.credentials(HTTP_AUTHORIZATION="Basic dXNlcjpwYXNzd29yZA==")
        res2 = self.client.get("/api/auth/profile/")
        self.assertEqual(res2.status_code, 401)

        # 3. Empty Bearer string
        self.client.credentials(HTTP_AUTHORIZATION="Bearer ")
        res3 = self.client.get("/api/auth/profile/")
        self.assertEqual(res3.status_code, 401)

        # 4. Tampered valid token (flip signature bytes)
        login_res = self.client.post(
            "/api/auth/login/",
            {
                "username": "e2e_driver",
                "password": "StrongPassword123!@#",
            },
            format="json",
        )
        valid_access = login_res.data["data"]["access"]
        tampered_access = valid_access[:-5] + "XXXXX"
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tampered_access}")
        res4 = self.client.get("/api/auth/profile/")
        self.assertEqual(res4.status_code, 401)

    def test_52_empty_and_malformed_request_payloads(self):
        """TEST-52: Verify empty and malformed request payloads are safely handled with proper status codes."""
        self.client.credentials()

        # 1. Empty body to login
        res_login_empty = self.client.post("/api/auth/login/", {}, format="json")
        self.assertEqual(res_login_empty.status_code, 400)
        self.assertFalse(res_login_empty.data["success"])
        self.assertEqual(res_login_empty.data["message"], "Invalid request data.")
        self.assertIn("errors", res_login_empty.data)
        self.assertIn("username", res_login_empty.data["errors"])
        self.assertIn("password", res_login_empty.data["errors"])

        # 2. Empty body to register
        res_reg_empty = self.client.post("/api/auth/register/", {}, format="json")
        self.assertEqual(res_reg_empty.status_code, 400)
        self.assertFalse(res_reg_empty.data["success"])
        self.assertIn("username", res_reg_empty.data["errors"])
        self.assertIn("password", res_reg_empty.data["errors"])

        # 3. Empty body to token refresh
        res_ref_empty = self.client.post("/api/auth/token/refresh/", {}, format="json")
        self.assertEqual(res_ref_empty.status_code, 400)
        self.assertFalse(res_ref_empty.data["success"])
        self.assertIn("refresh", res_ref_empty.data["errors"])

        # 4. Authenticated logout with empty body
        login_res = self.client.post(
            "/api/auth/login/",
            {
                "username": "e2e_driver",
                "password": "StrongPassword123!@#",
            },
            format="json",
        )
        access_token = login_res.data["data"]["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        res_logout_empty = self.client.post("/api/auth/logout/", {}, format="json")
        self.assertEqual(res_logout_empty.status_code, 400)
        self.assertFalse(res_logout_empty.data["success"])
        self.assertIn("refresh", res_logout_empty.data["errors"])

        # 5. Invalid data types to login
        self.client.credentials()
        res_invalid_types = self.client.post(
            "/api/auth/login/",
            {"username": 12345, "password": None},
            format="json",
        )
        self.assertEqual(res_invalid_types.status_code, 400)
        self.assertFalse(res_invalid_types.data["success"])
        self.assertEqual(res_invalid_types.data["message"], "Invalid request data.")

    def test_53_model_default_role_is_ambulance_driver(self):
        """TEST-53: Verify User model default role is AMBULANCE_DRIVER, not ADMIN."""
        # Create user without passing 'role'
        implicit_user = User.objects.create_user(
            username="implicit_driver_user",
            password="StrongPassword123!@#",
        )
        self.assertEqual(implicit_user.role, UserRole.AMBULANCE_DRIVER)
        self.assertNotEqual(implicit_user.role, UserRole.ADMIN)
        self.assertTrue(implicit_user.is_ambulance_driver)
        self.assertFalse(implicit_user.is_system_admin)

        # Confirm explicitly created ADMIN users still retain their ADMIN role
        self.assertEqual(self.admin_user.role, UserRole.ADMIN)
        self.assertTrue(self.admin_user.is_system_admin)

    def test_54_framework_401_response_envelope(self):
        """TEST-54: Verify framework-level 401 errors are wrapped in SERTOS standard envelope."""
        self.client.credentials()
        res = self.client.get("/api/auth/profile/")
        self.assertEqual(res.status_code, 401)
        self.assertFalse(res.data["success"])
        self.assertEqual(res.data["data"], {})
        self.assertIn("Authentication credentials were not provided.", res.data["message"])
        self.assertIn("errors", res.data)
        self.assertIn("detail", res.data)
        self.assertIn("timestamp", res.data)

    def test_55_framework_403_response_envelope(self):
        """TEST-55: Verify framework-level 403 errors are wrapped in SERTOS standard envelope."""
        req = self.factory.get("/test/hospital/")
        req.user = self.driver_user
        force_authenticate(req, user=self.driver_user)
        response = _TestHospitalOnlyView.as_view()(req)
        self.assertEqual(response.status_code, 403)
        self.assertFalse(response.data["success"])
        self.assertEqual(response.data["data"], {})
        self.assertIn("Access denied: Hospital Emergency Staff credentials required.", response.data["message"])
        self.assertIn("errors", response.data)
        self.assertIn("detail", response.data)
        self.assertIn("timestamp", response.data)

    def test_56_framework_405_response_envelope(self):
        """TEST-56: Verify framework-level 405 Method Not Allowed errors are wrapped in SERTOS envelope."""
        res = self.client.get("/api/auth/login/")
        self.assertEqual(res.status_code, 405)
        self.assertFalse(res.data["success"])
        self.assertEqual(res.data["data"], {})
        self.assertIn('Method "GET" not allowed.', res.data["message"])
        self.assertIn("errors", res.data)
        self.assertIn("timestamp", res.data)

    def test_57_framework_404_response_envelope(self):
        """TEST-57: Verify framework-level 404 Not Found errors are wrapped in SERTOS envelope."""
        from django.http import Http404
        from rest_framework.permissions import AllowAny

        class _TestNotFoundView(APIView):
            permission_classes = [AllowAny]

            def get(self, request):
                raise Http404("Emergency resource not found.")

        req = self.factory.get("/test/not-found/")
        response = _TestNotFoundView.as_view()(req)
        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.data["success"])
        self.assertEqual(response.data["data"], {})
        self.assertIn("Emergency resource not found.", response.data["message"])
        self.assertIn("errors", response.data)
        self.assertIn("timestamp", response.data)


class HealthCheckEndpointTests(TestCase):
    """Verifies production health-check and readiness probes."""

    def setUp(self):
        self.client = APIClient()

    def test_health_check_root_endpoint(self):
        """GET /health/ returns 200 OK with healthy database status."""
        response = self.client.get("/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "healthy")
        self.assertEqual(response.data["database"], "connected")
        self.assertEqual(response.data["service"], "sertos-backend")
        self.assertIn("timestamp", response.data)

    def test_health_check_api_endpoint(self):
        """GET /api/health/ returns 200 OK without requiring authentication."""
        response = self.client.get("/api/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "healthy")
        self.assertEqual(response.data["database"], "connected")




