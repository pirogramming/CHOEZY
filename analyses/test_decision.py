from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from alternatives.models import (
    Alternative,
    AlternativeItem,
    Category,
    LLMRequestLog,
)
from core.gemini import GeminiRequestError, GeminiTimeoutError
from products.models import Consideration

from .models import Decision


class DecisionAPITests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="decision_user",
            email="decision@example.com",
            password="StrongPass!2468",
            name="의사결정 사용자",
            birth_date=date(2000, 1, 1),
            gender="FEMALE",
            spending_type=["VALUE", "CAUTIOUS"],
            value_criteria=["PRICE", "UTILIZATION"],
            monthly_budget="300K_500K",
        )
        self.category = Category.objects.get(code=Category.Code.LIVING)
        self.consideration = Consideration.objects.create(
            user=self.user,
            product_name="테스트 노트북",
            product_price=1_200_000,
            purpose=Consideration.Purpose.SELF_DEVELOPMENT,
            status=Consideration.Status.GENERATED,
        )
        self.consideration.categories.add(self.category)
        for slot in range(1, 4):
            item = AlternativeItem.objects.create(
                category=self.category,
                name=f"생활 대안 {slot}",
                unit_label="회",
                average_price=100_000 * slot,
                calc_type=AlternativeItem.CalcType.UNIT_PRICE,
                source_name="테스트 출처",
                source_url="https://example.com/source",
                effective_date=date(2026, 8, 3),
            )
            Alternative.objects.create(
                consideration=self.consideration,
                category=self.category,
                item=item,
                slot=slot,
                unit_price=item.average_price,
                duration=f"{slot}개월",
                expected_effect=f"기대 효과 {slot}",
                ai_reason=f"추천 이유 {slot}",
                result_type=Alternative.ResultType.QUANTITY,
                equivalent_quantity=12,
                display_text=f"생활 대안 {slot} 약 12회",
            )
        self.url = (
            f"/api/analyses/considerations/{self.consideration.pk}/decision/"
        )
        self.client.force_login(self.user)

    def ai_response(self):
        return {
            "purpose_fit": "HIGH",
            "expected_satisfaction": "MIDDLE",
            "recommendation": "LOW",
            "key_points": [
                "공부 목적에 성능이 충분합니다.",
                "월 예산 대비 부담이 큽니다.",
                "동일 비용으로 다른 경험도 가능합니다.",
            ],
            "summary": "목적에는 맞지만 예산 부담이 커 보류를 권합니다.",
        }

    @patch("analyses.services.GeminiDecisionAdvisor.advise")
    def test_creates_decision_with_display_values(self, advise):
        advise.return_value = self.ai_response()

        response = self.client.post(
            self.url, data={}, content_type="application/json"
        )

        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["purpose_fit"], "HIGH")
        self.assertEqual(body["purpose_fit_display"], "높음")
        self.assertEqual(body["expected_satisfaction_display"], "중간")
        self.assertEqual(body["recommendation_display"], "낮음")
        self.assertEqual(len(body["key_points"]), 3)
        self.assertEqual(body["consideration_id"], self.consideration.pk)

        gauge = body["chart"]["gauge"]
        self.assertEqual(gauge["level"], "HIGH")
        self.assertEqual(gauge["score"], 88)
        self.assertAlmostEqual(gauge["angle_deg"], 158.4)

        bars = body["chart"]["bars"]
        self.assertEqual(
            [bar["key"] for bar in bars],
            ["purpose_fit", "expected_satisfaction", "recommendation"],
        )
        self.assertEqual([bar["score"] for bar in bars], [88, 55, 32])

        decision = Decision.objects.get(consideration=self.consideration)
        self.assertEqual(decision.key_points, body["key_points"])
        self.assertTrue(
            LLMRequestLog.objects.filter(
                consideration=self.consideration,
                purpose=LLMRequestLog.Purpose.DECISION,
                status=LLMRequestLog.Status.SUCCESS,
            ).exists()
        )

    @patch("analyses.services.GeminiDecisionAdvisor.advise")
    def test_prompt_carries_calculated_opportunity_cost(self, advise):
        advise.return_value = self.ai_response()

        self.client.post(self.url, data={}, content_type="application/json")

        prompt = advise.call_args.args[0]
        self.assertIn("생활 대안 1 약 12회", prompt)
        self.assertIn("테스트 노트북", prompt)

    @patch("analyses.services.GeminiDecisionAdvisor.advise")
    def test_rejects_second_creation(self, advise):
        advise.return_value = self.ai_response()
        self.client.post(self.url, data={}, content_type="application/json")

        response = self.client.post(
            self.url, data={}, content_type="application/json"
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.json()["error"]["code"], "ALREADY_EXISTS"
        )
        self.assertEqual(
            Decision.objects.filter(
                consideration=self.consideration
            ).count(),
            1,
        )

    @patch("analyses.services.GeminiDecisionAdvisor.advise")
    def test_rejects_draft_status(self, advise):
        advise.return_value = self.ai_response()
        self.consideration.status = Consideration.Status.DRAFT
        self.consideration.save(update_fields=["status"])

        response = self.client.post(
            self.url, data={}, content_type="application/json"
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.json()["error"]["code"], "INVALID_STATUS"
        )
        advise.assert_not_called()

    @patch("analyses.services.GeminiDecisionAdvisor.advise")
    def test_rejects_invalid_level(self, advise):
        advise.return_value = {**self.ai_response(), "purpose_fit": "VERY"}

        response = self.client.post(
            self.url, data={}, content_type="application/json"
        )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(
            response.json()["error"]["code"], "AI_REQUEST_FAILED"
        )
        self.assertFalse(Decision.objects.exists())
        self.assertTrue(
            LLMRequestLog.objects.filter(
                status=LLMRequestLog.Status.FAILED
            ).exists()
        )

    @patch("analyses.services.GeminiDecisionAdvisor.advise")
    def test_rejects_wrong_key_point_count(self, advise):
        advise.return_value = {**self.ai_response(), "key_points": ["하나"]}

        response = self.client.post(
            self.url, data={}, content_type="application/json"
        )

        self.assertEqual(response.status_code, 502)
        self.assertFalse(Decision.objects.exists())

    @patch("analyses.services.GeminiDecisionAdvisor.advise")
    def test_truncates_long_key_point(self, advise):
        advise.return_value = {
            **self.ai_response(),
            "key_points": ["가" * 200, "짧은 문장", "또 다른 문장"],
        }

        response = self.client.post(
            self.url, data={}, content_type="application/json"
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(response.json()["key_points"][0]), 100)

    @patch("analyses.services.GeminiDecisionAdvisor.advise")
    def test_returns_504_on_timeout(self, advise):
        advise.side_effect = GeminiTimeoutError("시간 초과")

        response = self.client.post(
            self.url, data={}, content_type="application/json"
        )

        self.assertEqual(response.status_code, 504)
        self.assertEqual(response.json()["error"]["code"], "AI_TIMEOUT")

    @patch("analyses.services.GeminiDecisionAdvisor.advise")
    def test_returns_502_on_request_error(self, advise):
        advise.side_effect = GeminiRequestError("호출 실패")

        response = self.client.post(
            self.url, data={}, content_type="application/json"
        )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(
            response.json()["error"]["code"], "AI_REQUEST_FAILED"
        )

    def test_get_returns_404_before_creation(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "NOT_FOUND")

    @patch("analyses.services.GeminiDecisionAdvisor.advise")
    def test_get_returns_existing_decision(self, advise):
        advise.return_value = self.ai_response()
        created = self.client.post(
            self.url, data={}, content_type="application/json"
        ).json()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), created)

    @patch("analyses.services.GeminiDecisionAdvisor.advise")
    def test_other_users_consideration_is_not_found(self, advise):
        advise.return_value = self.ai_response()
        other = get_user_model().objects.create_user(
            username="other_user",
            email="other@example.com",
            password="StrongPass!2468",
            name="다른 사용자",
            birth_date=date(1999, 5, 5),
            gender="MALE",
            spending_type=["QUALITY"],
            value_criteria=["QUALITY"],
            monthly_budget="500K_1M",
        )
        self.client.force_login(other)

        response = self.client.post(
            self.url, data={}, content_type="application/json"
        )

        self.assertEqual(response.status_code, 404)
        advise.assert_not_called()

    def test_requires_login(self):
        self.client.logout()

        response = self.client.post(
            self.url, data={}, content_type="application/json"
        )

        self.assertEqual(response.status_code, 403)


class DecisionPageTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="page_user",
            email="page@example.com",
            password="StrongPass!2468",
            name="페이지 사용자",
            birth_date=date(2000, 1, 1),
            gender="OTHER",
            spending_type=["EXPERIENCE"],
            value_criteria=["SATISFACTION"],
            monthly_budget="100K_300K",
        )
        self.consideration = Consideration.objects.create(
            user=self.user,
            product_name="테스트 태블릿",
            product_price=800_000,
            purpose=Consideration.Purpose.HOBBY,
            status=Consideration.Status.GENERATED,
        )
        self.url = f"/analyses/considerations/{self.consideration.pk}/decision/"

    def test_redirects_anonymous_user(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    def test_renders_create_button_without_decision(self):
        self.client.force_login(self.user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["decision_data"])
        self.assertTrue(response.context["can_create_decision"])
        self.assertContains(response, "decision-create-btn")

    def test_hides_create_button_before_alternatives_exist(self):
        self.client.force_login(self.user)
        self.consideration.status = Consideration.Status.DRAFT
        self.consideration.save(update_fields=["status"])

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["can_create_decision"])
        self.assertNotContains(response, "decision-create-btn")

    def test_renders_existing_decision(self):
        self.client.force_login(self.user)
        Decision.objects.create(
            consideration=self.consideration,
            purpose_fit=Decision.Level.MIDDLE,
            expected_satisfaction=Decision.Level.HIGH,
            recommendation=Decision.Level.MIDDLE,
            key_points=["근거 1", "근거 2", "근거 3"],
            summary="종합 설명",
            ai_model="gemini-test",
        )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["can_create_decision"])
        self.assertEqual(
            response.context["decision_data"]["chart"]["gauge"]["score"], 55
        )
        # 화면에 하드코딩된 값이 아니라 실제 데이터가 렌더되는지 확인한다
        self.assertContains(response, "근거 1")
        self.assertContains(response, "종합 설명")
        # 바늘 회전은 브라우저 JS가 data-angle을 읽어 계산한다
        self.assertContains(response, 'data-angle="99.0"')
        self.assertContains(response, "height:55%")
        self.assertContains(response, "height:88%")
        self.assertNotContains(response, "현재 사용자는 업무 생산성을")

    def test_other_users_consideration_is_404(self):
        other = get_user_model().objects.create_user(
            username="page_other",
            email="page_other@example.com",
            password="StrongPass!2468",
            name="다른 사용자",
            birth_date=date(1998, 3, 3),
            gender="MALE",
            spending_type=["ASSET"],
            value_criteria=["PRICE"],
            monthly_budget="OVER_2M",
        )
        self.client.force_login(other)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 404)
