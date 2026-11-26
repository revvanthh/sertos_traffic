"""
Models for SERTOS AI Emergency Agent application (Phase 8.1.3).

Implements:
1. VoiceAgentSession: Persistent voice interaction session linking an authenticated
   ambulance driver to chronological conversation turns and extracted triage data.
"""

import uuid
from django.conf import settings
from django.db import models


class SessionStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    COMPLETED = "COMPLETED", "Completed"
    ABANDONED = "ABANDONED", "Abandoned"


class VoiceAgentSession(models.Model):
    """
    Tracks a voice AI conversation session for an authenticated ambulance driver.
    Maintains chronological conversation history, extracted triage entities,
    and missing information state between turns.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique UUID identifier for the voice agent session.",
    )
    driver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="voice_agent_sessions",
        help_text="Authenticated, verified ambulance driver owning this session.",
    )
    status = models.CharField(
        max_length=20,
        choices=SessionStatus.choices,
        default=SessionStatus.ACTIVE,
        db_index=True,
        help_text="Current operational status of this voice session.",
    )
    conversation_history = models.JSONField(
        default=list,
        blank=True,
        help_text="Chronological list of conversation turns [{role, message, timestamp}].",
    )
    extracted_emergency_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Aggregated structured emergency data extracted across turns.",
    )
    missing_information = models.JSONField(
        default=list,
        blank=True,
        help_text="List of required triage fields not yet provided by the driver.",
    )
    needs_confirmation = models.BooleanField(
        default=False,
        help_text="Flag indicating critical triage data is collected and awaiting driver confirmation.",
    )
    associated_incident = models.ForeignKey(
        "emergencies.EmergencyIncident",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="voice_sessions",
        help_text="Optional emergency incident associated with or created via this voice session.",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Timestamp when voice session was initiated.",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp of the latest interaction in this session.",
    )
    ended_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when voice session transitioned to COMPLETED or ABANDONED.",
    )

    class Meta:
        db_table = "agent_voice_session"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["driver", "status"], name="idx_agent_driver_status"),
        ]

    def __str__(self) -> str:
        return f"VoiceSession {self.id} ({self.driver.username}) - {self.status}"
