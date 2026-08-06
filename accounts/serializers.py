from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
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


class MyBasicInfoUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["username", "name", "birth_date", "gender"]
        extra_kwargs = {
            "username": {"required": False},
            "name": {"required": False},
            "birth_date": {"required": False},
            "gender": {"required": False},
        }

    def validate_username(self, value):
        username = value.strip()
        if User.objects.filter(username__iexact=username).exclude(
            pk=self.instance.pk
        ).exists():
            raise serializers.ValidationError("이미 사용 중인 아이디입니다.")
        return username

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("수정할 정보를 입력해주세요.")
        return attrs


class ConsumerProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["spending_type", "value_criteria", "monthly_budget"]
        extra_kwargs = {
            "spending_type": {"required": False},
            "value_criteria": {"required": False},
            "monthly_budget": {"required": False},
        }

    def validate_spending_type(self, values):
        if not 1 <= len(values) <= 2:
            raise serializers.ValidationError(
                "소비 성향은 1개 이상 2개 이하로 선택해야 합니다."
            )
        if len(values) != len(set(values)):
            raise serializers.ValidationError(
                "소비 성향은 중복해서 선택할 수 없습니다."
            )
        return values

    def validate_value_criteria(self, values):
        if not 1 <= len(values) <= 3:
            raise serializers.ValidationError(
                "중요 가치 기준은 1개 이상 3개 이하로 선택해야 합니다."
            )
        if len(values) != len(set(values)):
            raise serializers.ValidationError(
                "중요 가치 기준은 중복해서 선택할 수 없습니다."
            )
        return values

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("수정할 소비 프로필을 입력해주세요.")
        return attrs


class PasswordChangeSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    password_confirm = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
    )

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError(
                {"password_confirm": "비밀번호가 일치하지 않습니다."}
            )
        validate_password(attrs["password"], user=self.context["request"].user)
        return attrs

    def save(self, **kwargs):
        user = self.context["request"].user
        user.set_password(self.validated_data["password"])
        user.save(update_fields=["password"])
        return user
