from django.urls import path

from . import views


app_name = "analyses"

urlpatterns = [
    # AI 구매 의사결정 (docs/API.md §10)
    path(
        "considerations/<int:pk>/decision/",
        views.decision,
        name="decision",
    ),

    # 화면 작업용 임시 라우트
    path("category/", views.category_select, name="category_select"),
    path("criteria/", views.criteria_select, name="criteria_select"),
    path("result/", views.result, name="result"),
]
