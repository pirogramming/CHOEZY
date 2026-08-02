from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from alternatives.models import Category

from .models import Consideration


User = get_user_model()


class ConsiderationCreateViewTests(TestCase):
    """구매 고민 입력 폼 (docs/API.md §5.1)."""

    def setUp(self):
        self.url = reverse("products:consideration_create")
        self.password = "StrongPass!2468"
        self.user = User.objects.create_user(
            username="choezy_user",
            email="user@example.com",
            password=self.password,
            name="최지",
            birth_date="2000-01-01",
            gender=User.Gender.OTHER,
            spending_type=[User.SpendingType.VALUE],
            value_criteria=[User.ValueCriterion.PRICE],
            monthly_budget=User.MonthlyBudget.FROM_300K_TO_500K,
        )
        self.categories = list(
            Category.objects.filter(is_active=True).order_by("display_order")
        )

    def login(self):
        self.client.force_login(self.user)

    def payload(self, **overrides):
        data = {
            "product_name": "아이패드 프로 11인치",
            "product_price": "2200000",
            "product_features": "M4 칩, 256GB",
            "product_url": "https://example.com/ipad",
            "purpose": Consideration.Purpose.DEVELOPMENT,
            "purpose_detail": "",
            "exclude_category": "",
            "categories": [self.categories[0].pk],
            "compare_criteria": [Consideration.CompareCriterion.PRICE],
        }
        data.update(overrides)

        return data

    def test_미로그인이면_로그인_페이지로_리다이렉트한다(self):
        response = self.client.get(self.url)

        # 로그인 페이지를 실제로 열어봅니다. LOGIN_URL이 없는 경로를 가리키면
        # 여기서 잡힙니다.
        self.assertRedirects(
            response,
            f"{settings.LOGIN_URL}?next={self.url}",
        )

    def test_로그인하면_입력_화면이_렌더된다(self):
        self.login()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "products/consideration_form.html")

    def test_구매_목적은_빈_선택지_없는_라디오로_렌더된다(self):
        self.login()

        response = self.client.get(self.url)
        purpose = response.context["form"].fields["purpose"]

        self.assertIsInstance(purpose.widget, forms.RadioSelect)
        self.assertEqual(purpose.label, "구매 목적")
        self.assertEqual(
            [value for value, _ in purpose.choices],
            [value for value, _ in Consideration.Purpose.choices],
        )

    def test_폼_필드_순서는_문서와_같다(self):
        self.login()

        response = self.client.get(self.url)

        self.assertEqual(
            list(response.context["form"].fields),
            [
                "product_name",
                "product_price",
                "product_features",
                "product_url",
                "purpose",
                "purpose_detail",
                "exclude_category",
                "categories",
                "compare_criteria",
            ],
        )

    def test_유효한_입력이면_고민을_생성하고_대안_페이지로_이동한다(self):
        self.login()

        response = self.client.post(self.url, self.payload())

        consideration = Consideration.objects.get()
        self.assertEqual(consideration.user, self.user)
        self.assertEqual(consideration.product_name, "아이패드 프로 11인치")
        self.assertEqual(consideration.product_price, 2200000)
        self.assertEqual(consideration.status, Consideration.Status.DRAFT)
        self.assertEqual(
            consideration.compare_criteria,
            [Consideration.CompareCriterion.PRICE],
        )
        self.assertRedirects(
            response,
            f"/alternatives/considerations/{consideration.pk}/",
            fetch_redirect_response=False,
        )

    def test_가격이_0이면_필드_에러다(self):
        self.login()

        response = self.client.post(self.url, self.payload(product_price="0"))

        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response.context["form"],
            "product_price",
            "가격은 1원 이상이어야 합니다.",
        )
        self.assertFalse(Consideration.objects.exists())

    def test_가격에_천_단위_구분_기호가_있으면_필드_에러다(self):
        self.login()

        response = self.client.post(
            self.url,
            self.payload(product_price="2,200,000"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response.context["form"],
            "product_price",
            "가격은 숫자만 입력해 주세요.",
        )

    def test_목적이_기타인데_직접_입력이_없으면_non_field_에러다(self):
        self.login()

        response = self.client.post(
            self.url,
            self.payload(purpose=Consideration.Purpose.ETC),
        )

        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response.context["form"],
            None,
            "구매 목적을 '기타'로 선택하면 목적을 직접 입력해야 합니다.",
        )

    def test_카테고리를_4개_선택하면_에러다(self):
        self.login()

        over_limit = settings.MAX_CATEGORY_SELECTION + 1
        response = self.client.post(
            self.url,
            self.payload(
                categories=[
                    category.pk for category in self.categories[:over_limit]
                ],
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response.context["form"],
            "categories",
            f"카테고리는 최대 {settings.MAX_CATEGORY_SELECTION}개까지 "
            "선택할 수 있습니다.",
        )

    def test_카테고리가_비어_있으면_필수_에러다(self):
        self.login()

        response = self.client.post(self.url, self.payload(categories=[]))

        self.assertEqual(response.status_code, 200)
        self.assertIn("categories", response.context["form"].errors)

    def test_비활성_카테고리는_선택할_수_없다(self):
        self.login()

        inactive = self.categories[0]
        inactive.is_active = False
        inactive.save(update_fields=["is_active"])

        response = self.client.post(
            self.url,
            self.payload(categories=[inactive.pk]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("categories", response.context["form"].errors)

    def test_다른_사용자의_고민으로_저장되지_않는다(self):
        self.login()

        self.client.post(
            self.url,
            self.payload(product_name="다른 상품"),
        )

        self.assertEqual(
            Consideration.objects.filter(user=self.user).count(),
            1,
        )
