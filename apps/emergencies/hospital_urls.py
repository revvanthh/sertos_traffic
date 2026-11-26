"""
URL routing configuration for Hospital Emergency Dashboard APIs.

Routes:
1. /api/hospital/incidents/           (GET: list hospital incidents)
2. /api/hospital/incidents/<uuid:pk>/ (GET: retrieve hospital incident details)
"""

from django.urls import path
from .views import HospitalIncidentDetailView, HospitalIncidentListView

app_name = "hospital"

urlpatterns = [
    path("incidents/", HospitalIncidentListView.as_view(), name="incident_list"),
    path("incidents/<uuid:pk>/", HospitalIncidentDetailView.as_view(), name="incident_detail"),
]
