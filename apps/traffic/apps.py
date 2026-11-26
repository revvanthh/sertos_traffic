"""
Django application configuration for SERTOS Traffic app.
"""

from django.apps import AppConfig


class TrafficConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.traffic"
    verbose_name = "Traffic Signal & ESP32 IoT Integration"
