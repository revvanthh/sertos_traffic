from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ("emergencies", "0005_emergencyevent_notification_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="HospitalBed",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("bed_number", models.CharField(max_length=30)),
                ("category", models.CharField(choices=[("GENERAL", "General"), ("ICU", "ICU"), ("EMERGENCY", "Emergency")], max_length=20)),
                ("status", models.CharField(choices=[("AVAILABLE", "Available"), ("OCCUPIED", "Occupied"), ("RESERVED", "Reserved")], default="AVAILABLE", max_length=20)),
                ("patient_label", models.CharField(blank=True, default="", max_length=150)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("hospital", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="beds", to="emergencies.hospital")),
            ],
            options={"db_table": "emergencies_hospital_bed", "ordering": ["bed_number"]},
        ),
        migrations.CreateModel(
            name="HospitalIncidentResponse",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("decision", models.CharField(choices=[("ACCEPTED", "Accepted"), ("REJECTED", "Rejected")], max_length=20)),
                ("reason", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("hospital", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="incident_responses", to="emergencies.hospital")),
                ("incident", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="hospital_response", to="emergencies.emergencyincident")),
                ("responded_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
            ],
            options={"db_table": "emergencies_hospital_incident_response"},
        ),
        migrations.AddConstraint(
            model_name="hospitalbed",
            constraint=models.UniqueConstraint(fields=("hospital", "bed_number"), name="unique_hospital_bed_number"),
        ),
    ]
