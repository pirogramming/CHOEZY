"""JSON API URL 모음 (docs/API.md §2.2).

페이지(HTML)는 각 앱의 `urls.py`, JSON API는 `api_urls.py`에 둡니다.
"""

from django.urls import include, path


urlpatterns = [
    path("accounts/", include("accounts.api_urls")),
    path("products/", include("products.api_urls")),
    path("alternatives/", include("alternatives.urls")),
    path("analyses/", include("analyses.urls")),
]
