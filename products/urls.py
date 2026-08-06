from django.urls import path, include

from .views import ConsiderationCreateView

from . import views

app_name = "products"


urlpatterns = [
    path(
        "considerations/new/",
        ConsiderationCreateView.as_view(),
        name="consideration_create",
    ),
        path(
        "comparison/<int:pk>/",
        views.comparison_table_view,
        name="comparison_table"
    ),

]
