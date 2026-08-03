from django.urls import path

from .views import (
    login_view,
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
