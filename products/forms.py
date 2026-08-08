from django import forms
from django.conf import settings

from alternatives.models import Category

from .models import Consideration


class ConsiderationForm(forms.ModelForm):
    product_price = forms.IntegerField(
        label="가격",
        min_value=1,
        error_messages={
            "min_value": "가격은 1원 이상이어야 합니다.",
            "invalid": "가격은 숫자만 입력해 주세요.",
        },
        widget=forms.TextInput(
            attrs={
                "inputmode": "numeric",
                "autocomplete": "off",
                "placeholder": "상품의 가격을 입력해주세요.",
                "data-price-input": "",
            },
        ),
    )
    purpose = forms.ChoiceField(
        label="구매 목적",
        choices=[
            choice
            for choice in Consideration.Purpose.choices
            if choice[0] != Consideration.Purpose.ETC
        ],
        widget=forms.RadioSelect,
        required=False,
    )
    categories = forms.ModelMultipleChoiceField(
        label="비교 분야",
        queryset=Category.objects.filter(is_active=True),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        help_text=(
            f"최대 {settings.MAX_CATEGORY_SELECTION}개까지 선택할 수 있습니다."
        ),
    )
    category_detail = forms.CharField(
        label="비교 분야 직접 입력",
        max_length=50,
        required=False,
        widget=forms.TextInput(
            attrs={"placeholder": "예: 전자기기, 문화, 생활 편의"},
        ),
    )

    class Meta:
        model = Consideration
        fields = [
            "product_url",
            "product_name",
            "product_price",
            "purpose",
            "purpose_detail",
            "categories",
            "category_detail",
        ]
        labels = {
            "product_url": "상품 URL",
            "product_name": "상품명",
            "purpose_detail": "구매 목적 직접 입력",
        }
        widgets = {
            "product_url": forms.URLInput(
                attrs={"placeholder": "상품의 URL을 입력해주세요."},
            ),
            "product_name": forms.TextInput(
                attrs={"placeholder": "고민 중인 상품명을 입력해주세요."},
            ),
            "purpose_detail": forms.TextInput(
                attrs={"placeholder": "구매 목적을 직접 입력해주세요."},
            ),
        }

    def clean_categories(self):
        return list(self.cleaned_data["categories"])

    def clean(self):
        cleaned_data = super().clean()
        purpose = cleaned_data.get("purpose")
        purpose_detail = (cleaned_data.get("purpose_detail") or "").strip()
        categories = cleaned_data.get("categories") or []
        category_detail = (cleaned_data.get("category_detail") or "").strip()

        if purpose_detail:
            cleaned_data["purpose"] = Consideration.Purpose.ETC
            cleaned_data["purpose_detail"] = purpose_detail
        elif not purpose:
            self.add_error("purpose", "구매 목적을 선택하거나 직접 입력해주세요.")

        if category_detail:
            aliases = {
                "여행": Category.Code.TRAVEL,
                "운동": Category.Code.HEALTH,
                "건강": Category.Code.HEALTH,
                "운동건강": Category.Code.HEALTH,
                "문화": Category.Code.CULTURE,
                "여가": Category.Code.CULTURE,
                "문화여가": Category.Code.CULTURE,
                "생활": Category.Code.LIVING,
                "생활편의": Category.Code.LIVING,
                "디지털": Category.Code.DIGITAL,
                "전자기기": Category.Code.DIGITAL,
                "디지털전자기기": Category.Code.DIGITAL,
                "재정": Category.Code.FINANCE,
                "금융": Category.Code.FINANCE,
            }
            normalized = "".join(category_detail.lower().split()).replace("·", "")
            category_code = aliases.get(normalized)
            category = Category.objects.filter(
                code=category_code,
                is_active=True,
            ).first()
            if not category:
                self.add_error(
                    "category_detail",
                    "현재 지원하는 비교 분야를 입력해주세요.",
                )
            elif category not in categories:
                categories.append(category)

        if not categories:
            self.add_error("categories", "비교 분야를 1개 이상 선택해주세요.")
        elif len(categories) > settings.MAX_CATEGORY_SELECTION:
            self.add_error(
                "categories",
                f"비교 분야는 최대 {settings.MAX_CATEGORY_SELECTION}개까지 "
                "선택할 수 있습니다.",
            )
        cleaned_data["categories"] = categories
        return cleaned_data
