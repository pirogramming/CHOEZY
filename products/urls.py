from django.urls import path, include

from .views import ConsiderationCreateView

from . import views
from .views import opportunity_cost_view

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
        
    path(
        "opportunity-cost/<int:pk>/",
        opportunity_cost_view,
        name="opportunity_cost"
    ),
    
    path(
        "consumption-log/",
        views.consumption_log,
        name="consumption_log",
    ),

    path(
        "report/",
        views.choezy_report,
        name="choezy_report",
    ),
    path(
        "guideline/",
        views.guideline,
        name="guideline",
    ),

]