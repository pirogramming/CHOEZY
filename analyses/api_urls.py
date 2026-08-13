from django.urls import path

from .api_views import (
    DecisionAPIView,
    SpendingRecordAPIView,
    SpendingRecordListAPIView,
    SpendingStatsAPIView,
)


app_name = "analyses_api"

urlpatterns = [
    path(
        "considerations/<int:pk>/decision/",
        DecisionAPIView.as_view(),
        name="decision",
    ),
    path(
        "considerations/<int:pk>/spending-record/",
        SpendingRecordAPIView.as_view(),
        name="spending_record",
    ),
    path(
        "spending-records/",
        SpendingRecordListAPIView.as_view(),
        name="spending_record_list",
    ),
    path(
        "spending-records/stats/",
        SpendingStatsAPIView.as_view(),
        name="spending_record_stats",
    ),
]
