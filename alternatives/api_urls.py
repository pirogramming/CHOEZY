from django.urls import path

from .api_views import (
    AlternativeComparisonAPIView,
    AlternativeGenerateAPIView,
    AlternativeListAPIView,
    AlternativeRegenerateAPIView,
)


app_name = "alternatives_api"

urlpatterns = [
    path(
        "considerations/<int:pk>/generate/",
        AlternativeGenerateAPIView.as_view(),
        name="generate",
    ),
    path(
        "considerations/<int:pk>/comparison/",
        AlternativeComparisonAPIView.as_view(),
        name="comparison",
    ),
    path(
        "considerations/<int:pk>/",
        AlternativeListAPIView.as_view(),
        name="list",
    ),
    path(
        "<int:pk>/regenerate/",
        AlternativeRegenerateAPIView.as_view(),
        name="regenerate",
    ),
]
