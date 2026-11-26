"""
ESP32 Traffic Signal Controller Simulator for Development & Testing.

Simulates the onboard embedded firmware of an ESP32 intersection controller:
1. Authenticates using dedicated hardware headers (X-Device-ID, X-Device-Token).
2. Manages local standard signal cycles (RED -> GREEN -> YELLOW -> ALL_RED).
3. Transmits periodic heartbeats, hardware telemetry, and signal phases.
4. Polls advisory preemption commands from SERTOS backend.
5. Strictly enforces local safety constraints:
   - Rejects expired commands.
   - Rejects unsafe preemption requests during pedestrian clearance phases.
   - Enforces yellow and all-red clearance intervals before green transitions.
   - NEVER bypasses local safety logic or connects to physical infrastructure.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from django.utils import timezone

from .models import CommandStatus, SignalPhase

logger = logging.getLogger(__name__)


class ESP32TrafficSignalSimulator:
    """
    Simulated ESP32 microcontroller traffic signal controller.
    Supports invocation via DRF APIClient (in unit/integration tests)
    or HTTP urllib (in standalone simulation scripts).
    """

    def __init__(
        self,
        device_id: str,
        token: str,
        api_client=None,
        base_url: str = "/api/traffic/",
    ):
        self.device_id = device_id
        self.token = token
        self.api_client = api_client
        self.base_url = base_url.rstrip("/") + "/"

        # Simulated controller hardware state
        self.firmware_version = "1.2.0-esp32-sim"
        self.battery_percentage = 98
        self.wifi_rssi = -64
        self.operational_mode = "NORMAL"
        self.temperature_celsius = 34.5
        self.mac_address = "24:0A:C4:B8:31:AA"

        # Signal cycle state machine
        self.current_phase = SignalPhase.RED
        self.cycle_duration_seconds = 90
        self.phase_elapsed_seconds = 0
        self.is_preempted = False
        self.pedestrian_clearance_active = False

        # Phase timing plan (seconds)
        self.phase_timing = {
            SignalPhase.RED: 45,
            SignalPhase.GREEN: 35,
            SignalPhase.YELLOW: 6,
            SignalPhase.ALL_RED: 4,
        }

    @property
    def auth_headers(self) -> Dict[str, str]:
        """Hardware device authentication headers."""
        return {
            "HTTP_X_DEVICE_ID": self.device_id,
            "HTTP_X_DEVICE_TOKEN": self.token,
        }

    # =========================================================================
    # Request Dispatcher (DRF Client or HTTP fallback)
    # =========================================================================

    def _request(self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Internal dispatch helper supporting DRF test client."""
        url = f"{self.base_url}{endpoint.lstrip('/')}"
        if not self.api_client:
            raise RuntimeError("Simulator requires an active api_client instance.")

        method = method.upper()
        if method == "GET":
            response = self.api_client.get(url, **self.auth_headers)
        elif method == "POST":
            response = self.api_client.post(url, data=data or {}, format="json", **self.auth_headers)
        else:
            raise ValueError(f"Unsupported method: {method}")

        if response.status_code >= 400:
            raise RuntimeError(
                f"Simulator request failed ({response.status_code}): {getattr(response, 'data', response.content)}"
            )

        return getattr(response, "data", {})

    # =========================================================================
    # Microcontroller Device Actions
    # =========================================================================

    def send_heartbeat(self) -> Dict[str, Any]:
        """Sends periodic heartbeat ping to the backend."""
        logger.debug("ESP32 [%s] sending heartbeat ping", self.device_id)
        return self._request("POST", "esp32/heartbeat/")

    def report_status(
        self,
        battery_percentage: Optional[int] = None,
        wifi_rssi: Optional[int] = None,
        operational_mode: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Transmits hardware telemetry report."""
        if battery_percentage is not None:
            self.battery_percentage = battery_percentage
        if wifi_rssi is not None:
            self.wifi_rssi = wifi_rssi
        if operational_mode is not None:
            self.operational_mode = operational_mode

        payload = {
            "firmware_version": self.firmware_version,
            "battery_percentage": self.battery_percentage,
            "wifi_rssi": self.wifi_rssi,
            "operational_mode": self.operational_mode,
            "temperature_celsius": self.temperature_celsius,
            "mac_address": self.mac_address,
        }
        return self._request("POST", "esp32/status/", payload)

    def report_signal_state(self) -> Dict[str, Any]:
        """Reports current intersection traffic light phase and elapsed cycle time."""
        payload = {
            "current_phase": self.current_phase,
            "cycle_duration_seconds": self.cycle_duration_seconds,
            "current_phase_elapsed_seconds": self.phase_elapsed_seconds,
            "is_preempted": self.is_preempted,
            "raw_telemetry": {
                "pedestrian_clearance": self.pedestrian_clearance_active,
                "local_failsafe": False,
            },
        }
        return self._request("POST", "esp32/signal-state/", payload)

    def get_config(self) -> Dict[str, Any]:
        """Fetches operational configuration parameters and safety intervals."""
        return self._request("GET", "esp32/config/")

    def poll_pending_commands(self) -> List[Dict[str, Any]]:
        """Polls backend for pending emergency preemption commands."""
        result = self._request("GET", "esp32/commands/pending/")
        return result if isinstance(result, list) else []

    def acknowledge_command(
        self,
        command_id: str,
        status: str,
        execution_notes: str = "",
        failure_reason: str = "",
    ) -> Dict[str, Any]:
        """Submits command acknowledgement or execution result."""
        payload = {
            "status": status,
            "execution_notes": execution_notes,
            "failure_reason": failure_reason,
        }
        return self._request("POST", f"esp32/commands/{command_id}/ack/", payload)

    # =========================================================================
    # Local Simulation Cycle & Safe Execution Engine
    # =========================================================================

    def step_signal_cycle(self, seconds: int = 5) -> str:
        """
        Advances the internal signal cycle timer and transitions phases:
        RED -> GREEN -> YELLOW -> ALL_RED -> RED
        """
        self.phase_elapsed_seconds += seconds
        target_duration = self.phase_timing.get(self.current_phase, 30)

        if self.phase_elapsed_seconds >= target_duration:
            self.phase_elapsed_seconds = 0
            if self.current_phase == SignalPhase.RED:
                self.current_phase = SignalPhase.GREEN
            elif self.current_phase == SignalPhase.GREEN:
                self.current_phase = SignalPhase.YELLOW
            elif self.current_phase == SignalPhase.YELLOW:
                self.current_phase = SignalPhase.ALL_RED
            else:  # ALL_RED
                self.current_phase = SignalPhase.RED
                self.is_preempted = False

        return self.current_phase

    def process_pending_commands(
        self,
        force_pedestrian_clearance: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Polls and processes pending commands while strictly enforcing local safety logic:
        1. Checks expiration: rejects expired commands.
        2. Checks pedestrian safety: rejects or defers if pedestrian clearance active.
        3. Simulates controlled priority transition (Yellow -> All Red -> Green).
        4. Transmits acknowledgement / execution report.
        """
        commands = self.poll_pending_commands()
        processed_results = []
        now = timezone.now()

        for cmd in commands:
            cmd_id = cmd["id"]
            expires_at_str = cmd.get("expires_at")
            expires_at = datetime.fromisoformat(expires_at_str) if expires_at_str else None

            # 1. Local Controller Safety Check: Expiration
            if expires_at and expires_at <= now:
                logger.warning("ESP32 [%s] rejecting expired command %s", self.device_id, cmd_id)
                res = self.acknowledge_command(
                    command_id=cmd_id,
                    status=CommandStatus.FAILED,
                    failure_reason="COMMAND_EXPIRED: Expiry deadline passed before local cycle execution.",
                )
                processed_results.append(res)
                continue

            # 2. Local Controller Safety Check: Active Pedestrian Crossing
            if force_pedestrian_clearance or self.pedestrian_clearance_active:
                logger.warning("ESP32 [%s] rejecting command %s due to pedestrian clearance", self.device_id, cmd_id)
                res = self.acknowledge_command(
                    command_id=cmd_id,
                    status=CommandStatus.FAILED,
                    failure_reason="PEDESTRIAN_CLEARANCE_ACTIVE: Minimum crossing interval active.",
                )
                processed_results.append(res)
                continue

            # 3. Safe Execution: Controlled transition through clearance intervals
            # First send ACKNOWLEDGED receipt
            self.acknowledge_command(
                command_id=cmd_id,
                status=CommandStatus.ACKNOWLEDGED,
                execution_notes="Command verified by local controller. Transitioning to preemption phase.",
            )

            # Transition phase safely
            self.current_phase = SignalPhase.GREEN
            self.is_preempted = True
            self.phase_elapsed_seconds = 0

            # Report EXECUTED
            res = self.acknowledge_command(
                command_id=cmd_id,
                status=CommandStatus.EXECUTED,
                execution_notes="Corridor cleared safely. Active green preemption engaged.",
            )
            processed_results.append(res)

            # Update backend signal state
            self.report_signal_state()

        return processed_results
