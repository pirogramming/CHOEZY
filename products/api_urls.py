from django.urls import path

from .api_views import ProductPreviewAPIView


app_name = "products_api"


urlpatterns = [
    path(
        "preview/",
        ProductPreviewAPIView.as_view(),
        name="preview",
    ),
]
