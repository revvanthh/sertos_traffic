"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static
from config.views import HealthCheckView
from config.views import frontend_view, static_asset_not_found
from apps.accounts.views import AdminOverviewView, UserVerificationView

urlpatterns = [
    path('health/', HealthCheckView.as_view(), name='health_root'),
    path('api/health/', HealthCheckView.as_view(), name='health_api'),
    path('admin/', admin.site.urls),
    path('api/auth/', include('apps.accounts.urls')),
    path('api/admin/overview/', AdminOverviewView.as_view(), name='admin-overview'),
    path('api/admin/users/<int:user_id>/verification/', UserVerificationView.as_view(), name='admin-user-verification'),
    path('api/emergencies/', include('apps.emergencies.urls')),
    path('api/hospital/', include('apps.emergencies.hospital_urls')),
    path('api/police/', include('apps.emergencies.police_urls')),
    path('api/notifications/', include('apps.emergencies.notification_urls')),
    path('api/traffic/', include('apps.traffic.urls')),
    path('api/agent/', include('apps.agent.urls')),
    path('static/<path:path>', static_asset_not_found, name='missing_static_asset'),
    path('', frontend_view, name='frontend'),
    path('<path:path>', frontend_view, name='frontend_spa'),
]

if settings.DEBUG:
    urlpatterns = static(settings.STATIC_URL, document_root=settings.STATIC_ROOT) + urlpatterns
