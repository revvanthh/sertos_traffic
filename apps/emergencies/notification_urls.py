"""
URL routing configuration for SERTOS Notifications.

Endpoints:
1. GET   /api/notifications/          (List user notifications, paginated)
2. PATCH /api/notifications/read-all/ (Mark all unread notifications as read)
3. GET   /api/notifications/<pk>/     (Retrieve notification detail)
4. PATCH /api/notifications/<pk>/read/ (Mark single notification as read)
"""

from django.urls import path
from .views import (
    NotificationDetailView,
    NotificationListView,
    NotificationMarkReadAllView,
    NotificationMarkReadView,
)

app_name = "notifications"

urlpatterns = [
    path("", NotificationListView.as_view(), name="notification_list"),
    path("read-all/", NotificationMarkReadAllView.as_view(), name="notification_read_all"),
    path("<uuid:pk>/", NotificationDetailView.as_view(), name="notification_detail"),
    path("<uuid:pk>/read/", NotificationMarkReadView.as_view(), name="notification_mark_read"),
]
