from django.urls import path

from .views import (
    login_view,
    logout_view,
    profile_view,
    signup_profile_view,
    signup_view,
)

app_name = "accounts"

urlpatterns = [
    path(
        "login/",
        login_view,
        name="login",
    ),
    path(
        "logout/",
        logout_view,
        name="logout",
    ),
    path(
        "profile/",
        profile_view,
        name="profile",
    ),
    path(
        "signup/",
        signup_view,
        name="signup",
    ),
    path(
        "signup/profile/",
        signup_profile_view,
        name="signup_profile",
    ),
]
