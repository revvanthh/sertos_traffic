from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import UserRole
from apps.emergencies.models import Ambulance, Hospital


class AdminOverviewApiTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(
            username="overview-admin",
            password="test-password-only",
            role=UserRole.ADMIN,
        )
        self.driver = User.objects.create_user(
            username="overview-driver",
            password="test-password-only",
            role=UserRole.AMBULANCE_DRIVER,
            is_verified=False,
            email="driver@example.test",
        )
        self.ambulance = Ambulance.objects.create(
            vehicle_number="TEST-AMB-01",
            vehicle_type="Basic Life Support",
            assigned_driver=self.driver,
        )
        Hospital.objects.create(
            name="Test Emergency Hospital",
            hospital_code="TEST-HOSP-01",
            address="Test address",
        )
        self.client = APIClient()

    def test_admin_receives_summary_and_limited_user_and_fleet_data(self):
        self.client.force_authenticate(user=self.admin)

        response = self.client.get("/api/admin/overview/")

        self.assertEqual(response.status_code, 200)
        data = response.data["data"]
        self.assertEqual(data["summary"]["registered_users"], 2)
        self.assertEqual(data["summary"]["pending_verification"], 1)
        self.assertEqual(data["summary"]["active_ambulances"], 1)
        self.assertEqual(data["summary"]["active_hospitals"], 1)
        self.assertEqual(data["ambulances"][0]["id"], str(self.ambulance.id))
        driver = next(user for user in data["users"] if user["username"] == "overview-driver")
        self.assertFalse(driver["is_verified"])
        self.assertNotIn("password", driver)
        self.assertNotIn("phone_number", driver)

    def test_non_admin_cannot_read_admin_overview(self):
        self.client.force_authenticate(user=self.driver)

        response = self.client.get("/api/admin/overview/")

        self.assertEqual(response.status_code, 403)

    def test_anonymous_user_cannot_read_admin_overview(self):
        response = self.client.get("/api/admin/overview/")

        self.assertEqual(response.status_code, 401)
