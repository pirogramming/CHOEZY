from django.contrib.auth import get_user_model
from rest_framework import serializers


User = get_user_model()


class UsernameAvailabilitySerializer(serializers.Serializer):
    username = serializers.CharField(
        max_length=User._meta.get_field("username").max_length,
        validators=User._meta.get_field("username").validators,
    )


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "name",
            "birth_date",
            "gender",
            "spending_type",
            "value_criteria",
            "monthly_budget",
        ]
        read_only_fields = fields
