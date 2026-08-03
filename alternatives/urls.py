from django.urls import path
from . import views

app_name = "alternatives"

urlpatterns = [
    path("categories/", views.category_alternatives, name="category_alternatives"),
]