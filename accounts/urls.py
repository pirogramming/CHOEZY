from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    LoginView,
    LogoutView,
    MyInfoView,
    SignupView,
    UsernameAvailabilityView,
)


app_name = "accounts"


urlpatterns = [
    path(
        "signup/",
        SignupView.as_view(),
        name="signup",
    ),
    path(
        "check-username/",
        UsernameAvailabilityView.as_view(),
        name="check-username",
    ),
    path(
        "login/",
        LoginView.as_view(),
        name="login",
    ),
    path(
        "token/refresh/",
        TokenRefreshView.as_view(),
        name="token-refresh",
    ),
    path(
        "logout/",
        LogoutView.as_view(),
        name="logout",
    ),
    path(
        "me/",
        MyInfoView.as_view(),
        name="me",
    ),
]
