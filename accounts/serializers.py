from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework.validators import UniqueValidator


User = get_user_model()


class SignupSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(
        validators=[
            UniqueValidator(
                queryset=User.objects.all(),
                lookup="iexact",
                message="이미 사용 중인 이메일입니다.",
            ),
        ],
    )
    password = serializers.CharField(
        write_only=True,
        style={"input_type": "password"},
    )
    password_confirm = serializers.CharField(
        write_only=True,
        style={"input_type": "password"},
    )

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
            "password",
            "password_confirm",
        ]
        read_only_fields = [
            "id",
        ]
        extra_kwargs = {
            "birth_date": {
                "required": True,
                "allow_null": False,
            },
            "gender": {
                "required": True,
                "allow_blank": False,
            },
            "spending_type": {
                "required": True,
                "allow_empty": False,
            },
            "value_criteria": {
                "required": True,
                "allow_empty": False,
            },
            "monthly_budget": {
                "required": True,
                "allow_blank": False,
            },
        }

    def validate_email(self, value):
        return value.strip().lower()

    def validate_value_criteria(self, value):
        if len(value) > 3:
            raise serializers.ValidationError(
                "중요 가치 기준은 최대 3개까지 선택할 수 있습니다."
            )

        if len(value) != len(set(value)):
            raise serializers.ValidationError(
                "중요 가치 기준은 중복해서 선택할 수 없습니다."
            )

        return value

    def validate_spending_type(self, value):
        if len(value) > 2:
            raise serializers.ValidationError(
                "소비 성향은 최대 2개까지 선택할 수 있습니다."
            )

        if len(value) != len(set(value)):
            raise serializers.ValidationError(
                "소비 성향은 중복해서 선택할 수 없습니다."
            )

        return value

    def validate(self, attrs):
        password = attrs.get("password")

        if password != attrs.get("password_confirm"):
            raise serializers.ValidationError(
                {
                    "password_confirm": "비밀번호가 일치하지 않습니다.",
                }
            )

        user = User(
            username=attrs.get("username", ""),
            email=attrs.get("email", ""),
            name=attrs.get("name", ""),
        )

        try:
            validate_password(password, user=user)
        except DjangoValidationError as error:
            raise serializers.ValidationError(
                {"password": list(error.messages)}
            ) from error

        return attrs

    def create(self, validated_data):
        validated_data.pop("password_confirm")

        password = validated_data.pop("password")

        return User.objects.create_user(
            password=password,
            **validated_data,
        )


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
