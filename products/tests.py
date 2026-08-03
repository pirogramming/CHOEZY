from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch

from alternatives.models import Category

from .models import Consideration
from .services import (
    ProductPreviewError,
    extract_product_metadata,
    validate_public_url,
)


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
            "product_url": "https://example.com/ipad",
            "product_name": "아이패드 프로 11인치",
            "product_price": "2200000",
            "purpose": Consideration.Purpose.WORK,
            "purpose_detail": "",
            "categories": [self.categories[0].pk],
            "category_detail": "",
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
            [
                value
                for value, _ in Consideration.Purpose.choices
                if value != Consideration.Purpose.ETC
            ],
        )

    def test_폼_필드_순서는_문서와_같다(self):
        self.login()

        response = self.client.get(self.url)

        self.assertEqual(
            list(response.context["form"].fields),
            [
                "product_url",
                "product_name",
                "product_price",
                "purpose",
                "purpose_detail",
                "categories",
                "category_detail",
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
            list(Consideration.CompareCriterion.values),
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

    def test_구매목적을_직접_입력하면_기타로_저장한다(self):
        self.login()

        response = self.client.post(
            self.url,
            self.payload(purpose="", purpose_detail="반려동물 돌봄"),
        )

        self.assertEqual(response.status_code, 302)
        consideration = Consideration.objects.get()
        self.assertEqual(consideration.purpose, Consideration.Purpose.ETC)
        self.assertEqual(consideration.purpose_detail, "반려동물 돌봄")

    def test_구매목적_선택과_직접입력이_모두_비어있으면_에러다(self):
        self.login()

        response = self.client.post(
            self.url,
            self.payload(purpose="", purpose_detail=""),
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("purpose", response.context["form"].errors)

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
            f"비교 분야는 최대 {settings.MAX_CATEGORY_SELECTION}개까지 "
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

    def test_비교분야_직접입력을_지원_카테고리로_변환한다(self):
        self.login()
        response = self.client.post(
            self.url,
            self.payload(categories=[], category_detail="전자기기"),
        )

        self.assertEqual(response.status_code, 302)
        consideration = Consideration.objects.get()
        self.assertEqual(
            list(consideration.categories.values_list("code", flat=True)),
            [Category.Code.DIGITAL],
        )

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


class ProductPreviewAPITests(TestCase):
    def setUp(self):
        self.url = reverse("products_api:preview")
        self.user = User.objects.create_user(
            username="preview_user",
            email="preview@example.com",
            password="StrongPass!2468",
            name="미리보기 사용자",
            birth_date="2000-01-01",
            gender=User.Gender.OTHER,
            spending_type=[User.SpendingType.VALUE],
            value_criteria=[User.ValueCriterion.PRICE],
            monthly_budget=User.MonthlyBudget.FROM_300K_TO_500K,
        )

    def test_미로그인_사용자는_URL을_조회할_수_없다(self):
        response = self.client.post(
            self.url,
            {"url": "https://shop.example.com/product/1"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)

    @patch("products.api_views.fetch_product_preview")
    def test_URL에서_추출한_상품명과_가격을_반환한다(self, fetch):
        self.client.force_login(self.user)
        fetch.return_value = {
            "product_name": "아이패드 프로",
            "product_price": 2_200_000,
            "image_url": "https://shop.example.com/ipad.jpg",
            "product_url": "https://shop.example.com/product/1",
        }

        response = self.client.post(
            self.url,
            {"url": "https://shop.example.com/product/1"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["product_name"], "아이패드 프로")
        self.assertEqual(response.json()["product_price"], 2_200_000)

    @patch("products.api_views.fetch_product_preview")
    def test_상품정보를_찾지_못하면_직접입력_안내를_반환한다(self, fetch):
        self.client.force_login(self.user)
        fetch.side_effect = ProductPreviewError(
            "PRODUCT_INFO_NOT_FOUND",
            "상품명 또는 가격을 찾지 못했습니다. 직접 입력해주세요.",
        )

        response = self.client.post(
            self.url,
            {"url": "https://shop.example.com/product/1"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "PRODUCT_INFO_NOT_FOUND")

    def test_유효하지_않은_URL은_거부한다(self):
        self.client.force_login(self.user)

        response = self.client.post(
            self.url,
            {"url": "not-a-url"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)


class ProductMetadataExtractionTests(TestCase):
    def test_내부망_URL은_거부한다(self):
        with self.assertRaises(ProductPreviewError) as context:
            validate_public_url("http://127.0.0.1:8000/admin/")

        self.assertEqual(context.exception.code, "PRIVATE_URL_NOT_ALLOWED")

    def test_OpenGraph_상품정보를_추출한다(self):
        html = """
            <html><head>
            <meta property="og:title" content="맥북 에어">
            <meta property="product:price:amount" content="1,790,000원">
            <meta property="og:image" content="/images/macbook.jpg">
            </head></html>
        """

        result = extract_product_metadata(html, "https://shop.example.com/item/1")

        self.assertEqual(result["product_name"], "맥북 에어")
        self.assertEqual(result["product_price"], 1_790_000)
        self.assertEqual(
            result["image_url"],
            "https://shop.example.com/images/macbook.jpg",
        )

    def test_JSON_LD_상품정보를_추출한다(self):
        html = """
            <script type="application/ld+json">
            {
              "@type": "Product",
              "name": "에어팟 4",
              "offers": {"@type": "Offer", "price": "199000"}
            }
            </script>
        """

        result = extract_product_metadata(html, "https://shop.example.com/item/2")

        self.assertEqual(result["product_name"], "에어팟 4")
        self.assertEqual(result["product_price"], 199_000)
