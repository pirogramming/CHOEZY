from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError


User = get_user_model()


class SignupForm(forms.ModelForm):
    password = forms.CharField(
        label="비밀번호",
        strip=False,
        widget=forms.PasswordInput,
    )
    password_confirm = forms.CharField(
        label="비밀번호 확인",
        strip=False,
        widget=forms.PasswordInput,
    )
    spending_type = forms.MultipleChoiceField(
        label="소비 성향",
        choices=User.SpendingType.choices,
    )
    value_criteria = forms.MultipleChoiceField(
        label="중요 가치 기준",
        choices=User.ValueCriterion.choices,
    )

    class Meta:
        model = User
        fields = [
            "username",
            "email",
            "name",
            "birth_date",
            "gender",
            "spending_type",
            "value_criteria",
            "monthly_budget",
        ]

    def clean_username(self):
        username = self.cleaned_data["username"].strip()

        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("이미 사용 중인 아이디입니다.")

        return username

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()

        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("이미 사용 중인 이메일입니다.")

        return email

    def clean_spending_type(self):
        values = self.cleaned_data["spending_type"]

        if not 1 <= len(values) <= 2:
            raise forms.ValidationError(
                "소비 성향은 1개 이상 2개 이하로 선택해야 합니다."
            )

        if len(values) != len(set(values)):
            raise forms.ValidationError(
                "소비 성향은 중복해서 선택할 수 없습니다."
            )

        return values

    def clean_value_criteria(self):
        values = self.cleaned_data["value_criteria"]

        if not 1 <= len(values) <= 3:
            raise forms.ValidationError(
                "중요 가치 기준은 1개 이상 3개 이하로 선택해야 합니다."
            )

        if len(values) != len(set(values)):
            raise forms.ValidationError(
                "중요 가치 기준은 중복해서 선택할 수 없습니다."
            )

        return values

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        password_confirm = cleaned_data.get("password_confirm")

        if password and password_confirm and password != password_confirm:
            self.add_error(
                "password_confirm",
                "비밀번호가 일치하지 않습니다.",
            )

        if password:
            user = User(
                username=cleaned_data.get("username", ""),
                email=cleaned_data.get("email", ""),
                name=cleaned_data.get("name", ""),
            )

            try:
                validate_password(password, user=user)
            except DjangoValidationError as error:
                self.add_error("password", error)

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])

        if commit:
            user.save()

        return user
