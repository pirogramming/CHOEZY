from django import forms
from django.conf import settings

from alternatives.models import Category

from .models import Consideration


class ConsiderationForm(forms.ModelForm):
    """구매 고민 입력 폼 (docs/API.md §5.1).

    상품명·가격을 포함한 상품 정보는 전부 사용자가 직접 입력합니다.
    `product_url`은 참고용 링크일 뿐 서버가 그 페이지를 읽어오지 않습니다.
    """

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
                "placeholder": "2200000",
                "data-price-input": "",
            },
        ),
    )

    # ModelForm이 자동 생성하면 빈 선택지("---------")가 라디오에 하나 더
    # 붙으므로 직접 선언합니다.
    purpose = forms.ChoiceField(
        label="구매 목적",
        choices=Consideration.Purpose.choices,
        widget=forms.RadioSelect,
    )

    exclude_category = forms.ModelChoiceField(
        label="상품 자체 카테고리",
        queryset=Category.objects.filter(is_active=True),
        required=False,
        empty_label="선택 안 함",
        help_text="이 카테고리는 대안 후보에서 제외됩니다.",
    )

    categories = forms.ModelMultipleChoiceField(
        label="비교할 카테고리",
        queryset=Category.objects.filter(is_active=True),
        widget=forms.CheckboxSelectMultiple,
        help_text=(
            f"최대 {settings.MAX_CATEGORY_SELECTION}개까지 선택할 수 있습니다."
        ),
    )

    compare_criteria = forms.MultipleChoiceField(
        label="비교 기준",
        choices=Consideration.CompareCriterion.choices,
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )

    class Meta:
        model = Consideration

        fields = [
            "product_name",
            "product_price",
            "product_features",
            "product_url",
            "purpose",
            "purpose_detail",
            "exclude_category",
            "categories",
            "compare_criteria",
        ]

        labels = {
            "product_name": "상품명",
            "product_features": "상품 특징",
            "product_url": "상품 페이지 링크",
            "purpose_detail": "목적 직접 입력",
        }

        widgets = {
            "product_name": forms.TextInput(
                attrs={
                    "placeholder": "예: 아이패드 프로 11인치",
                },
            ),
            "product_features": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "고민에 참고할 만한 특징을 적어 주세요.",
                },
            ),
            "product_url": forms.URLInput(
                attrs={
                    "placeholder": "https://",
                },
            ),
            "purpose_detail": forms.TextInput(
                attrs={
                    "placeholder": "'기타'를 선택했다면 목적을 적어 주세요.",
                },
            ),
        }

    def clean_categories(self):
        categories = self.cleaned_data["categories"]

        if len(categories) > settings.MAX_CATEGORY_SELECTION:
            raise forms.ValidationError(
                f"카테고리는 최대 {settings.MAX_CATEGORY_SELECTION}개까지 "
                "선택할 수 있습니다.",
            )

        return categories

    def clean(self):
        cleaned_data = super().clean()

        purpose = cleaned_data.get("purpose")
        purpose_detail = cleaned_data.get("purpose_detail")

        if purpose == Consideration.Purpose.ETC and not purpose_detail:
            raise forms.ValidationError(
                "구매 목적을 '기타'로 선택하면 목적을 직접 입력해야 합니다.",
            )

        return cleaned_data
