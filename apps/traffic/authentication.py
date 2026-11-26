"""
Cryptographic Device Authentication for ESP32 Traffic Signal Controllers.

Strictly isolates IoT hardware authentication from human JWT authentication:
1. Microcontrollers authenticate using dedicated hardware credentials:
   - Header: `X-Device-ID: <device_id>`
   - Header: `X-Device-Token: <secret_hardware_token>`
   - (Or Authorization header: `DeviceToken <device_id>:<secret_hardware_token>`)
2. Incoming tokens are verified in constant time against a one-way cryptographic SHA-256 hash.
3. Human JWT tokens are rejected on device endpoints.
4. Device tokens are rejected on human endpoints.
5. Inactive or decommissioned devices are strictly blocked (HTTP 403).
6. Secrets are never logged or returned in responses.
"""

import logging
from rest_framework import exceptions
from rest_framework.authentication import BaseAuthentication

from .models import TrafficDevice

logger = logging.getLogger(__name__)


class ESP32DeviceAuthentication(BaseAuthentication):
    """
    Dedicated authentication scheme for ESP32 IoT traffic signal controllers.
    """

    def authenticate(self, request):
        device_id = request.headers.get("X-Device-ID")
        device_token = request.headers.get("X-Device-Token")

        # Fallback to Authorization: DeviceToken <device_id>:<token>
        auth_header = request.headers.get("Authorization")
        if not device_id and auth_header:
            parts = auth_header.split()
            if len(parts) == 2 and parts[0].lower() in ("devicetoken", "device"):
                creds = parts[1].split(":", 1)
                if len(creds) == 2:
                    device_id, device_token = creds[0], creds[1]

        # If neither header is present, return None to allow other authenticators or trigger permission error
        if not device_id and not device_token:
            return None

        # If one is provided but not both, reject immediately
        if not device_id or not device_token:
            raise exceptions.AuthenticationFailed(
                "Both 'X-Device-ID' and 'X-Device-Token' headers are required for device authentication."
            )

        try:
            device = TrafficDevice.objects.get(device_id=device_id)
        except TrafficDevice.DoesNotExist:
            logger.warning("ESP32 authentication failed: unknown device_id '%s'", device_id)
            raise exceptions.AuthenticationFailed("Invalid device credentials.")

        # Check active status: inactive devices cannot communicate
        if not device.is_active:
            logger.warning("ESP32 authentication blocked: device '%s' is inactive", device_id)
            raise exceptions.PermissionDenied("Device is inactive or decommissioned.")

        # Verify cryptographic token hash
        if not device.check_token(device_token):
            logger.warning("ESP32 authentication failed: invalid token for device '%s'", device_id)
            raise exceptions.AuthenticationFailed("Invalid device credentials.")

        # Return (principal, auth)
        return (device, device_token)

    def authenticate_header(self, request):
        return 'DeviceToken realm="sertos-esp32"'
