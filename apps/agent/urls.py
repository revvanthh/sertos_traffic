"""
URL routing configuration for SERTOS AI Emergency Agent endpoints (Phase 8.1.3).
"""

from django.urls import path
from .views import (
    VoiceSessionConfirmEmergencyView,
    VoiceSessionDetailView,
    VoiceSessionEndView,
    VoiceSessionListCreateView,
    VoiceSessionTurnView,
)

app_name = "agent"

urlpatterns = [
    path("sessions/", VoiceSessionListCreateView.as_view(), name="session_list_create"),
    path("sessions/<uuid:session_id>/", VoiceSessionDetailView.as_view(), name="session_detail"),
    path("sessions/<uuid:session_id>/turn/", VoiceSessionTurnView.as_view(), name="session_turn"),
    path("sessions/<uuid:session_id>/confirm-emergency/", VoiceSessionConfirmEmergencyView.as_view(), name="session_confirm_emergency"),
    path("sessions/<uuid:session_id>/end/", VoiceSessionEndView.as_view(), name="session_end"),
]
