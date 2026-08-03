from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from products.models import Consideration

from .ai_service import GeminiRequestError
from .models import Alternative, AlternativeItem, Category, LLMRequestLog


class AlternativeGenerationAPITests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="alternative_user",
            email="alternative@example.com",
            password="StrongPass!2468",
            name="대안 사용자",
            birth_date=date(2000, 1, 1),
            gender="FEMALE",
            spending_type=["VALUE", "CAUTIOUS"],
            value_criteria=["PRICE", "UTILIZATION"],
            monthly_budget="300K_500K",
        )
        self.category = Category.objects.get(code=Category.Code.LIVING)
        self.items = [
            AlternativeItem.objects.create(
                category=self.category,
                name=f"생활 대안 {index}",
                unit_label="회",
                average_price=10_000 * index,
                spec_note=f"테스트 기준 {index}",
                calc_type=AlternativeItem.CalcType.UNIT_PRICE,
                source_name="테스트 출처",
                source_url="https://example.com/source",
                effective_date=date(2026, 8, 3),
            )
            for index in range(1, 4)
        ]
        self.consideration = Consideration.objects.create(
            user=self.user,
            product_name="테스트 노트북",
            product_price=1_200_000,
            purpose=Consideration.Purpose.STUDY,
        )
        self.consideration.categories.add(self.category)
        self.url = (
            f"/api/alternatives/considerations/"
            f"{self.consideration.pk}/generate/"
        )
        self.client.force_login(self.user)

    def ai_response(self):
        return {
            "selections": [
                {
                    "category_code": self.category.code,
                    "items": [
                        {
                            "item_id": item.id,
                            "slot": slot,
                            "duration": f"{slot}개월",
                            "expected_effect": f"기대 효과 {slot}",
                            "ai_reason": f"추천 이유 {slot}",
                        }
                        for slot, item in enumerate(self.items, start=1)
                    ],
                }
            ]
        }

    def create_replacement_item(self):
        return AlternativeItem.objects.create(
            category=self.category,
            name="생활 대안 4",
            unit_label="회",
            average_price=40_000,
            spec_note="재생성 테스트 기준",
            calc_type=AlternativeItem.CalcType.UNIT_PRICE,
            source_name="테스트 출처",
            source_url="https://example.com/source-4",
            effective_date=date(2026, 8, 3),
        )

    def regeneration_response(self, item, slot=1):
        return {
            "selections": [
                {
                    "category_code": self.category.code,
                    "items": [
                        {
                            "item_id": item.id,
                            "slot": slot,
                            "duration": "4개월",
                            "expected_effect": "새로운 기대 효과",
                            "ai_reason": "기존 추천과 다른 새 대안입니다.",
                        }
                    ],
                }
            ]
        }

    @patch("alternatives.services.GeminiAlternativeSelector.select")
    def test_generates_three_alternatives_from_gemini_choices(self, select):
        select.return_value = self.ai_response()

        response = self.client.post(self.url, data={}, content_type="application/json")

        self.assertEqual(response.status_code, 201)
        self.consideration.refresh_from_db()
        self.assertEqual(
            self.consideration.status, Consideration.Status.GENERATED
        )
        alternatives = Alternative.objects.filter(
            consideration=self.consideration, is_current=True
        ).order_by("slot")
        self.assertEqual(alternatives.count(), 3)
        self.assertEqual(
            list(alternatives.values_list("item_id", flat=True)),
            [item.id for item in self.items],
        )
        self.assertEqual(alternatives[0].unit_price, 10_000)
        self.assertEqual(str(alternatives[0].equivalent_quantity), "120.00")
        self.assertEqual(response.json()["categories"][0]["alternatives"][0]["item"]["id"], self.items[0].id)
        self.assertEqual(
            LLMRequestLog.objects.get().status,
            LLMRequestLog.Status.SUCCESS,
        )
        self.assertIn("candidate", select.call_args.args[0])

    @patch("alternatives.services.GeminiAlternativeSelector.select")
    def test_rejects_item_id_not_in_candidates_and_rolls_back(self, select):
        payload = self.ai_response()
        payload["selections"][0]["items"][0]["item_id"] = 999_999
        select.return_value = payload

        response = self.client.post(self.url, data={}, content_type="application/json")

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["error"]["code"], "AI_REQUEST_FAILED")
        self.assertFalse(
            Alternative.objects.filter(consideration=self.consideration).exists()
        )
        self.consideration.refresh_from_db()
        self.assertEqual(self.consideration.status, Consideration.Status.DRAFT)
        self.assertEqual(
            LLMRequestLog.objects.get().status,
            LLMRequestLog.Status.FAILED,
        )

    @patch("alternatives.services.GeminiAlternativeSelector.select")
    def test_does_not_generate_twice(self, select):
        select.return_value = self.ai_response()
        self.client.post(self.url, data={}, content_type="application/json")

        response = self.client.post(self.url, data={}, content_type="application/json")

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "INVALID_STATUS")
        self.assertEqual(select.call_count, 1)

    @patch("alternatives.services.GeminiAlternativeSelector.select")
    def test_returns_409_before_ai_when_candidates_are_insufficient(self, select):
        self.items[-1].delete()

        response = self.client.post(self.url, data={}, content_type="application/json")

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.json()["error"]["code"], "NO_CANDIDATE_ITEMS"
        )
        select.assert_not_called()

    @patch("alternatives.services.GeminiAlternativeSelector.select")
    def test_returns_502_and_logs_when_gemini_fails(self, select):
        select.side_effect = GeminiRequestError("호출 실패")

        response = self.client.post(self.url, data={}, content_type="application/json")

        self.assertEqual(response.status_code, 502)
        self.assertEqual(
            LLMRequestLog.objects.get().status,
            LLMRequestLog.Status.FAILED,
        )

    def test_requires_session_authentication(self):
        self.client.logout()

        response = self.client.post(self.url, data={}, content_type="application/json")

        self.assertEqual(response.status_code, 403)

    def test_list_returns_empty_categories_before_generation(self):
        response = self.client.get(
            f"/api/alternatives/considerations/{self.consideration.pk}/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["categories"], [])

    @patch("alternatives.services.GeminiAlternativeSelector.select")
    def test_list_returns_current_alternatives_without_calling_ai(self, select):
        select.return_value = self.ai_response()
        self.client.post(self.url, data={}, content_type="application/json")
        select.reset_mock()

        response = self.client.get(
            f"/api/alternatives/considerations/{self.consideration.pk}/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["categories"]), 1)
        self.assertEqual(
            len(response.json()["categories"][0]["alternatives"]), 3
        )
        select.assert_not_called()

    @patch("alternatives.services.GeminiAlternativeSelector.select")
    def test_regenerates_one_slot_and_preserves_history(self, select):
        select.return_value = self.ai_response()
        self.client.post(self.url, data={}, content_type="application/json")
        previous = Alternative.objects.get(
            consideration=self.consideration, slot=1, is_current=True
        )
        replacement = self.create_replacement_item()
        select.return_value = self.regeneration_response(replacement)

        response = self.client.post(
            f"/api/alternatives/{previous.pk}/regenerate/",
            data={},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        previous.refresh_from_db()
        self.assertFalse(previous.is_current)
        current = Alternative.objects.get(
            consideration=self.consideration, slot=1, is_current=True
        )
        self.assertEqual(current.item, replacement)
        self.assertEqual(current.version, 2)
        self.assertEqual(response.json()["previous_alternative_id"], previous.id)
        self.assertEqual(
            LLMRequestLog.objects.filter(
                purpose=LLMRequestLog.Purpose.REGENERATE,
                status=LLMRequestLog.Status.SUCCESS,
            ).count(),
            1,
        )

        history_response = self.client.get(
            f"/api/alternatives/considerations/{self.consideration.pk}/"
            "?include_history=true"
        )
        slot_one = history_response.json()["categories"][0]["alternatives"][0]
        self.assertEqual(slot_one["id"], current.id)
        self.assertEqual(slot_one["history"][0]["id"], previous.id)

    @patch("alternatives.services.GeminiAlternativeSelector.select")
    def test_regeneration_failure_keeps_previous_current(self, select):
        select.return_value = self.ai_response()
        self.client.post(self.url, data={}, content_type="application/json")
        previous = Alternative.objects.get(
            consideration=self.consideration, slot=1, is_current=True
        )
        self.create_replacement_item()
        select.side_effect = GeminiRequestError("재생성 실패")

        response = self.client.post(
            f"/api/alternatives/{previous.pk}/regenerate/",
            data={},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 502)
        previous.refresh_from_db()
        self.assertTrue(previous.is_current)
        self.assertEqual(
            Alternative.objects.filter(
                consideration=self.consideration, slot=1
            ).count(),
            1,
        )

    @patch("alternatives.services.GeminiAlternativeSelector.select")
    def test_regeneration_returns_409_when_no_unused_candidate_exists(
        self, select
    ):
        select.return_value = self.ai_response()
        self.client.post(self.url, data={}, content_type="application/json")
        previous = Alternative.objects.get(
            consideration=self.consideration, slot=1, is_current=True
        )
        select.reset_mock()

        response = self.client.post(
            f"/api/alternatives/{previous.pk}/regenerate/",
            data={},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.json()["error"]["code"], "NO_CANDIDATE_ITEMS"
        )
        select.assert_not_called()
