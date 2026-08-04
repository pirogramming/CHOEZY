from django.urls import path

from .views import (
    MyBasicInfoUpdateView,
    MyConsumerProfileUpdateView,
    MyInfoView,
    MyPasswordChangeView,
    UsernameAvailabilityView,
)


app_name = "accounts_api"


urlpatterns = [
    path(
        "check-username/",
        UsernameAvailabilityView.as_view(),
        name="check-username",
    ),
    path(
        "me/",
        MyInfoView.as_view(),
        name="me",
    ),
    path(
        "me/basic/",
        MyBasicInfoUpdateView.as_view(),
        name="me-basic",
    ),
    path(
        "me/password/",
        MyPasswordChangeView.as_view(),
        name="me-password",
    ),
    path(
        "me/profile/",
        MyConsumerProfileUpdateView.as_view(),
        name="me-profile",
    ),
]
