from django.urls import path
from . import views

app_name = "alternatives"

urlpatterns = [
    path(
        "considerations/<int:pk>/",
        views.category_alternatives,
        name="consideration_alternatives",
    ),
]
