from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import ProductPreviewRequestSerializer
from .services import ProductPreviewError, fetch_product_preview


class ProductPreviewAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ProductPreviewRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            preview = fetch_product_preview(serializer.validated_data["url"])
        except ProductPreviewError as error:
            if error.code in {"PRODUCT_INFO_NOT_FOUND", "SITE_ACCESS_BLOCKED"}:
                response_status = status.HTTP_422_UNPROCESSABLE_ENTITY
            elif error.code == "PRODUCT_FETCH_FAILED":
                response_status = status.HTTP_502_BAD_GATEWAY
            else:
                response_status = status.HTTP_400_BAD_REQUEST
            return Response(
                {"error": {"code": error.code, "message": error.message}},
                status=response_status,
            )
        return Response(preview, status=status.HTTP_200_OK)
