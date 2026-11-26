"""
URL routing configuration for the SERTOS Accounts application.

Maps authentication, token lifecycle, and user profile management
endpoints to their respective Django REST Framework class-based views.

Routes:
- POST /api/auth/login/         -> LoginView (name="login")
- POST /api/auth/token/refresh/ -> TokenRefreshView (name="token_refresh")
- POST /api/auth/logout/        -> LogoutView (name="logout")
- POST /api/auth/register/      -> RegisterView (name="register")
- GET/PATCH /api/auth/profile/  -> ProfileView (name="profile")
"""

from django.urls import path
from .views import (
    LoginView,
    TokenRefreshView,
    LogoutView,
    RegisterView,
    ProfileView,
)

urlpatterns = [
    path("login/", LoginView.as_view(), name="login"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("register/", RegisterView.as_view(), name="register"),
    path("profile/", ProfileView.as_view(), name="profile"),
]
