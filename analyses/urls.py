from django.urls import path
from . import views

app_name = "analyses"

urlpatterns = [
    path("category/", views.category_select, name="category_select"),
    path("criteria/", views.criteria_select, name="criteria_select"),
    path("comparison/", views.comparison, name="comparison"),
    path("result/", views.result, name="result"),
]