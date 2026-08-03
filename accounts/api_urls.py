from django.urls import path

from .views import (
    MyInfoView,
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
]
