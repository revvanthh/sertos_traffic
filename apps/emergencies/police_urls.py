"""
URL routing configuration for Police Traffic Dashboard APIs.

Routes:
1. /api/police/incidents/           (GET: list police traffic incidents)
2. /api/police/incidents/<uuid:pk>/ (GET: retrieve police traffic incident details)
"""

from django.urls import path
from .views import (
    PoliceIncidentAcknowledgementView,
    PoliceIncidentDetailView,
    PoliceIncidentListView,
)

app_name = "police"

urlpatterns = [
    path("incidents/", PoliceIncidentListView.as_view(), name="incident_list"),
    path("incidents/<uuid:pk>/", PoliceIncidentDetailView.as_view(), name="incident_detail"),
    path("incidents/<uuid:pk>/acknowledge/", PoliceIncidentAcknowledgementView.as_view(), name="incident_acknowledge"),
]
