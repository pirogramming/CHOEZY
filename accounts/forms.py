from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError


User = get_user_model()


class SignupBasicForm(forms.ModelForm):
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

    class Meta:
        model = User
        fields = [
            "name",
            "username",
            "email",
            "gender",
            "birth_date",
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

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        password_confirm = cleaned_data.get("password_confirm")

        if password and password_confirm and password != password_confirm:
            self.add_error("password_confirm", "비밀번호가 일치하지 않습니다.")

        if password:
            candidate = User(
                username=cleaned_data.get("username", ""),
                email=cleaned_data.get("email", ""),
                name=cleaned_data.get("name", ""),
            )
            try:
                validate_password(password, user=candidate)
            except DjangoValidationError as error:
                self.add_error("password", error)

        return cleaned_data


class SignupProfileForm(forms.Form):
    spending_type = forms.MultipleChoiceField(
        label="소비 성향",
        choices=User.SpendingType.choices,
    )
    value_criteria = forms.MultipleChoiceField(
        label="중요 가치 기준",
        choices=User.ValueCriterion.choices,
    )
    monthly_budget = forms.ChoiceField(
        label="월 소비 가능 예상 금액",
        choices=User.MonthlyBudget.choices,
    )

    def clean_spending_type(self):
        values = self.cleaned_data["spending_type"]
        if not 1 <= len(values) <= 2:
            raise forms.ValidationError(
                "소비 성향은 1개 이상 2개 이하로 선택해야 합니다."
            )
        if len(values) != len(set(values)):
            raise forms.ValidationError("소비 성향은 중복해서 선택할 수 없습니다.")
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
