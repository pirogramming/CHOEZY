from django.urls import path

from .api_views import AlternativeGenerateAPIView


app_name = "alternatives_api"

urlpatterns = [
    path(
        "considerations/<int:pk>/generate/",
        AlternativeGenerateAPIView.as_view(),
        name="generate",
    ),
]
