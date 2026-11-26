"""
URL routing configuration for SERTOS Emergencies application.

Routes:
1. /api/emergencies/                  (GET: list incidents, POST: report incident)
2. /api/emergencies/<uuid:pk>/        (GET: retrieve incident details)
3. /api/emergencies/<uuid:pk>/status/ (PATCH: update incident status)
4. /api/emergencies/<uuid:pk>/location/ (POST: submit GPS ping, GET: retrieve latest GPS ping)
5. /api/emergencies/<uuid:pk>/locations/ (GET: retrieve GPS ping history)
6. /api/emergencies/<uuid:pk>/route/   (GET: retrieve real-time road route, ETA, and polyline)
"""

from django.urls import path
from .views import (
    EmergencyIncidentDetailView,
    EmergencyIncidentListCreateView,
    EmergencyIncidentLocationHistoryView,
    EmergencyIncidentLocationView,
    EmergencyIncidentRouteView,
    EmergencyIncidentStatusUpdateView,
    HospitalListView,
    HospitalBedListView,
    HospitalBedDetailView,
    HospitalIncidentDecisionView,
)

app_name = "emergencies"

urlpatterns = [
    path("hospitals/", HospitalListView.as_view(), name="hospital_list"),
    path("hospital-beds/", HospitalBedListView.as_view(), name="hospital_bed_list"),
    path("hospital-beds/<uuid:pk>/", HospitalBedDetailView.as_view(), name="hospital_bed_detail"),
    path("hospital/incidents/<uuid:pk>/decision/", HospitalIncidentDecisionView.as_view(), name="hospital_incident_decision"),
    path("", EmergencyIncidentListCreateView.as_view(), name="incident_list_create"),
    path("<uuid:pk>/", EmergencyIncidentDetailView.as_view(), name="incident_detail"),
    path("<uuid:pk>/status/", EmergencyIncidentStatusUpdateView.as_view(), name="incident_status_update"),
    path("<uuid:pk>/location/", EmergencyIncidentLocationView.as_view(), name="incident_location"),
    path("<uuid:pk>/locations/", EmergencyIncidentLocationHistoryView.as_view(), name="incident_location_history"),
    path("<uuid:pk>/route/", EmergencyIncidentRouteView.as_view(), name="incident_route"),
]
