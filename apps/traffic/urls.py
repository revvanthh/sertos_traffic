"""
URL routing for SERTOS Traffic & ESP32 Integration.
"""

from django.urls import path

from .views import (
    AcknowledgeCommandView,
    DeviceConfigView,
    DeviceDetailView,
    DeviceHeartbeatView,
    DeviceListView,
    DeviceRegistrationView,
    DeviceSignalStateView,
    DeviceStatusView,
    PendingCommandsView,
    PoliceTrafficOverviewView,
    PoliceTrafficRecheckView,
)

app_name = "traffic"

urlpatterns = [
    path("police/overview/", PoliceTrafficOverviewView.as_view(), name="police-overview"),
    path("police/incidents/<uuid:incident_id>/recheck-corridor/", PoliceTrafficRecheckView.as_view(), name="police-recheck-corridor"),
    # Administrative Endpoints (Human Administrators)
    path("devices/", DeviceListView.as_view(), name="device-list"),
    path("devices/register/", DeviceRegistrationView.as_view(), name="device-register"),
    path("devices/<str:device_id>/", DeviceDetailView.as_view(), name="device-detail"),

    # Microcontroller IoT Endpoints (ESP32 Hardware Authentication)
    path("esp32/heartbeat/", DeviceHeartbeatView.as_view(), name="esp32-heartbeat"),
    path("esp32/status/", DeviceStatusView.as_view(), name="esp32-status"),
    path("esp32/config/", DeviceConfigView.as_view(), name="esp32-config"),
    path("esp32/signal-state/", DeviceSignalStateView.as_view(), name="esp32-signal-state"),
    path("esp32/commands/pending/", PendingCommandsView.as_view(), name="esp32-pending-commands"),
    path("esp32/commands/<uuid:command_id>/ack/", AcknowledgeCommandView.as_view(), name="esp32-ack-command"),
]
