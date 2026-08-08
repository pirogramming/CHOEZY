from rest_framework import serializers


class ProductPreviewRequestSerializer(serializers.Serializer):
    url = serializers.URLField(max_length=500)
