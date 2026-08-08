from django.urls import path

from .api_views import DecisionAPIView


app_name = "analyses_api"

urlpatterns = [
    path(
        "considerations/<int:pk>/decision/",
        DecisionAPIView.as_view(),
        name="decision",
    ),
]
