from datetime import date
from decimal import Decimal

from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from alternatives.models import Alternative, AlternativeItem, Category
from alternatives.visualization import format_quantity

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


class OpportunityCostViewTests(TestCase):
    """기회비용 시각화 페이지 (docs/API.md §7).

    비교표와 달리 서버가 컨텍스트를 완성해서 내려주는 페이지라, 응답
    HTML이 아니라 `response.context`를 검증합니다.
    """

    def setUp(self):
        self.password = "StrongPass!2468"
        self.user = self.create_user("choezy_user", "user@example.com")
        self.consideration = Consideration.objects.create(
            user=self.user,
            product_name="아이패드 프로 11인치",
            product_price=2_200_000,
            purpose=Consideration.Purpose.DEVELOPMENT,
            status=Consideration.Status.GENERATED,
        )
        self.url = reverse(
            "products:opportunity_cost",
            args=[self.consideration.pk],
        )
        self.living = Category.objects.get(code=Category.Code.LIVING)
        self.finance = Category.objects.get(code=Category.Code.FINANCE)

    def create_user(self, username, email):
        return get_user_model().objects.create_user(
            username=username,
            email=email,
            password=self.password,
            name="최지",
            birth_date="2000-01-01",
            gender=get_user_model().Gender.OTHER,
            spending_type=[get_user_model().SpendingType.VALUE],
            value_criteria=[get_user_model().ValueCriterion.PRICE],
            monthly_budget=get_user_model().MonthlyBudget.FROM_300K_TO_500K,
        )

    def create_item(self, category, name, unit_label, average_price, **extra):
        return AlternativeItem.objects.create(
            category=category,
            name=name,
            unit_label=unit_label,
            average_price=average_price,
            source_name="테스트 출처",
            source_url="https://example.com/source",
            effective_date=date(2026, 8, 3),
            **extra,
        )

    def create_quantity_alternative(self, slot, name, unit_label, unit_price):
        quantity = Decimal(self.consideration.product_price) / Decimal(
            unit_price
        )

        return Alternative.objects.create(
            consideration=self.consideration,
            category=self.living,
            item=self.create_item(self.living, name, unit_label, unit_price),
            slot=slot,
            unit_price=unit_price,
            result_type=Alternative.ResultType.QUANTITY,
            equivalent_quantity=quantity.quantize(Decimal("0.01")),
            display_text=f"{name} 약 {int(quantity)}{unit_label}",
        )

    def create_finance_alternative(self, slot=1):
        item = self.create_item(
            self.finance,
            "정기적금",
            "",
            10_000,
            calc_type=AlternativeItem.CalcType.SAVINGS,
            calc_params={"period_month": 12, "return_rate": 3.5},
        )

        return Alternative.objects.create(
            consideration=self.consideration,
            category=self.finance,
            item=item,
            slot=slot,
            unit_price=self.consideration.product_price,
            duration="12개월",
            expected_effect="월 183,333원씩 12개월 → 약 223만원",
            result_type=Alternative.ResultType.FUTURE_VALUE,
            future_value=2_237_500,
            display_text="정기적금 12개월 → 약 223만원",
        )

    def login(self):
        self.client.force_login(self.user)

    def test_미로그인이면_로그인_페이지로_리다이렉트한다(self):
        response = self.client.get(self.url)

        self.assertRedirects(
            response,
            f"{settings.LOGIN_URL}?next={self.url}",
        )

    def test_남의_고민이면_403이_아니라_404다(self):
        # 403으로 돌려주면 "그 id는 존재한다"는 사실이 새어 나갑니다.
        other = self.create_user("other_user", "other@example.com")
        self.client.force_login(other)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 404)

    def test_상품_가격은_만원_단위로_표기된다(self):
        self.login()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "products/opportunity_cost.html")
        self.assertEqual(response.context["product_price"], "220만원")

    def test_수량_환산_대안이_막대_데이터로_내려온다(self):
        self.login()
        self.create_quantity_alternative(1, "헬스장", "개월", 180_000)

        bar = self.client.get(self.url).context["opportunity_costs"][0]

        self.assertEqual(bar["name"], "헬스장")
        # 2,200,000 / 180,000 = 12.2222... → 저장 12.22, 표기는 내림해 12개월
        self.assertAlmostEqual(bar["count"], 12.22)
        self.assertEqual(bar["display_count"], "12개월")

    def test_수량이_1_미만이면_소수_첫째_자리까지_내림한다(self):
        self.login()
        self.create_quantity_alternative(1, "일본 여행", "회", 3_500_000)

        bar = self.client.get(self.url).context["opportunity_costs"][0]

        # 0.62857... → 저장 0.63 → 표기 0.6회
        self.assertEqual(bar["display_count"], "0.6회")

    def test_막대_색은_팔레트를_순환한다(self):
        self.login()
        for slot, price in enumerate([180_000, 220_000, 300_000], start=1):
            self.create_quantity_alternative(slot, f"대안 {slot}", "회", price)

        bars = self.client.get(self.url).context["opportunity_costs"]

        self.assertEqual(
            [bar["color"] for bar in bars],
            ["pink", "yellow", "orange"],
        )
        self.assertEqual(
            [bar["text_color"] for bar in bars],
            ["pink-text", "yellow-text", "orange-text"],
        )

    def test_재정_대안은_막대가_아니라_별도_목록으로_내려온다(self):
        self.login()
        self.create_quantity_alternative(1, "헬스장", "개월", 180_000)
        self.create_finance_alternative()

        context = self.client.get(self.url).context

        # 개수 개념이 없어 막대에 섞이면 안 됩니다.
        self.assertEqual(len(context["opportunity_costs"]), 1)
        self.assertEqual(
            context["financial_costs"],
            [
                {
                    "alternative_id": Alternative.objects.get(
                        category=self.finance
                    ).pk,
                    "category_name": self.finance.name,
                    "name": "정기적금",
                    "display_text": "정기적금 12개월 → 약 223만원",
                    "expected_effect": "월 183,333원씩 12개월 → 약 223만원",
                }
            ],
        )

    def test_이전_버전_대안은_그리지_않는다(self):
        self.login()
        outdated = self.create_quantity_alternative(1, "헬스장", "개월", 180_000)
        outdated.is_current = False
        outdated.save(update_fields=["is_current"])

        context = self.client.get(self.url).context

        self.assertEqual(context["opportunity_costs"], [])

    def test_대안이_없으면_빈_상태를_렌더한다(self):
        self.login()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["opportunity_costs"], [])
        self.assertContains(response, "아직 생성된 대안이 없어요")

    def test_대안_이름은_HTML로_렌더되지_않는다(self):
        self.login()
        self.create_quantity_alternative(
            1,
            "<script>alert(1)</script>",
            "회",
            180_000,
        )

        response = self.client.get(self.url)

        self.assertNotContains(response, "<script>alert(1)</script>")

    def test_data_count는_JS가_파싱할_수_있는_숫자다(self):
        self.login()
        self.create_quantity_alternative(1, "헬스장", "개월", 180_000)

        response = self.client.get(self.url)

        self.assertContains(response, 'data-count="12.22"')


class FormatQuantityTests(TestCase):
    """수량 표기 규칙 (docs/API.md §7.4) — 반올림이 아니라 내림."""

    def test_1_이상이면_정수로_내림한다(self):
        self.assertEqual(format_quantity(Decimal("12.22")), "12")
        self.assertEqual(format_quantity(Decimal("11.99")), "11")
        self.assertEqual(format_quantity(Decimal("1.00")), "1")

    def test_1_미만이면_소수_첫째_자리까지_내림한다(self):
        self.assertEqual(format_quantity(Decimal("0.68")), "0.6")
        self.assertEqual(format_quantity(Decimal("0.09")), "0.0")
