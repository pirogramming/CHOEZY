from django.urls import path

from .views import ConsiderationCreateView


app_name = "products"


urlpatterns = [
    path(
        "considerations/new/",
        ConsiderationCreateView.as_view(),
        name="consideration_create",
    ),
]
