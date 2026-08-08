from django.urls import path
from . import views

app_name = "alternatives"

urlpatterns = [
    path(
        "categories/<int:pk>/",
        views.category_alternatives,
        name="consideration_alternatives",
    ),
]