"""소비 패턴 분석 API 테스트 (docs/API.md §8.10)."""

from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from products.models import Consideration

from .ai_service import GeminiRequestError, GeminiTimeoutError
from .models import SpendingPatternReport, SpendingRecord


class SpendingPatternTestCase(TestCase):
    def setUp(self):
        self.user = self._create_user("pattern_user", "pattern@example.com")
        self.client.force_login(self.user)

    def _create_user(self, username, email):
        return get_user_model().objects.create_user(
            username=username,
            email=email,
            password="StrongPass!2468",
            name="테스트 사용자",
            birth_date=date(2000, 1, 1),
            gender="FEMALE",
            spending_type=["VALUE", "CAUTIOUS"],
            value_criteria=["PRICE", "UTILIZATION"],
            monthly_budget="300K_500K",
        )

    def _record(
        self,
        price=1_000_000,
        category="디지털·전자기기",
        purpose=Consideration.Purpose.SELF_DEVELOPMENT,
        satisfaction=4,
        purchase_status=SpendingRecord.PurchaseStatus.PURCHASED,
        recorded_on=None,
        user=None,
    ):
        owner = user or self.user
        consideration = Consideration.objects.create(
            user=owner,
            product_name=f"{category} 상품",
            product_price=price,
            purpose=purpose,
            status=Consideration.Status.DECIDED,
        )
        purchased = (
            purchase_status == SpendingRecord.PurchaseStatus.PURCHASED
        )
        day = recorded_on or date(2026, 8, 1)
        return SpendingRecord.objects.create(
            user=owner,
            consideration=consideration,
            purchase_status=purchase_status,
            recorded_on=day,
            purchased_on=day if purchased else None,
            satisfaction=satisfaction if purchased else None,
            category=category,
            product_name=consideration.product_name,
            product_price=price,
        )

    def _seed(self, count=3):
        for index in range(count):
            self._record(recorded_on=date(2026, 8, index + 1))

    def _url(self):
        return reverse("analyses_api:spending_pattern")

    def ai_response(self):
        return {
            "summary": (
                "목적이 분명한 소비일수록 만족도가 높고, 신중하게 비교한 "
                "후 구매하는 경향이 있어요"
            )
        }


class CreatePatternReportTests(SpendingPatternTestCase):
    @patch("analyses.ai_service.GeminiPatternAnalyst.analyze")
    def test_creates_report_from_statistics(self, analyze):
        analyze.return_value = self.ai_response()
        self._seed()

        response = self.client.post(self._url())

        self.assertEqual(response.status_code, 201)
        report = SpendingPatternReport.objects.get()
        self.assertEqual(report.user, self.user)
        self.assertEqual(report.record_count, 3)
        self.assertIn("만족도가 높고", report.summary)

    @patch("analyses.ai_service.GeminiPatternAnalyst.analyze")
    def test_prompt_carries_calculated_numbers(self, analyze):
        """비율·만족도는 §8.9가 이미 계산했으므로 근거로만 넣습니다."""
        analyze.return_value = self.ai_response()
        self._seed()

        self.client.post(self._url())

        prompt = analyze.call_args.args[0]
        self.assertIn("목적형_소비_비율_퍼센트", prompt)
        self.assertIn("가장_많이_소비한_분야", prompt)
        self.assertIn("평균_만족도", prompt)
        self.assertIn("새로운 수치를 만들지 마세요", prompt)

    @patch("analyses.ai_service.GeminiPatternAnalyst.analyze")
    def test_prompt_carries_consumer_profile(self, analyze):
        analyze.return_value = self.ai_response()
        self._seed()

        self.client.post(self._url())

        prompt = analyze.call_args.args[0]
        self.assertIn("가성비 중시", prompt)
        self.assertIn("신중한 소비 중시", prompt)

    @patch("analyses.ai_service.GeminiPatternAnalyst.analyze")
    def test_stores_evidence_snapshot(self, analyze):
        analyze.return_value = self.ai_response()
        self._seed()

        self.client.post(self._url())

        snapshot = SpendingPatternReport.objects.get().stats_snapshot
        self.assertEqual(snapshot["총_소비_기록_수"], 3)
        self.assertEqual(snapshot["가장_많이_소비한_분야"], "디지털·전자기기")

    @patch("analyses.ai_service.GeminiPatternAnalyst.analyze")
    def test_truncates_overlong_summary(self, analyze):
        analyze.return_value = {"summary": "가" * 500}
        self._seed()

        self.client.post(self._url())

        self.assertEqual(len(SpendingPatternReport.objects.get().summary), 200)

    @patch("analyses.ai_service.GeminiPatternAnalyst.analyze")
    def test_rejects_too_few_records(self, analyze):
        analyze.return_value = self.ai_response()
        self._seed(count=2)

        response = self.client.post(self._url())

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.json()["error"]["code"], "NOT_ENOUGH_RECORDS"
        )
        analyze.assert_not_called()

    @patch("analyses.ai_service.GeminiPatternAnalyst.analyze")
    def test_rejects_when_no_records_at_all(self, analyze):
        response = self.client.post(self._url())

        self.assertEqual(response.status_code, 409)
        analyze.assert_not_called()

    @patch("analyses.ai_service.GeminiPatternAnalyst.analyze")
    def test_returns_502_on_request_error(self, analyze):
        analyze.side_effect = GeminiRequestError("boom")
        self._seed()

        response = self.client.post(self._url())

        self.assertEqual(response.status_code, 502)
        self.assertEqual(
            response.json()["error"]["code"], "AI_REQUEST_FAILED"
        )
        self.assertFalse(SpendingPatternReport.objects.exists())

    @patch("analyses.ai_service.GeminiPatternAnalyst.analyze")
    def test_returns_504_on_timeout(self, analyze):
        analyze.side_effect = GeminiTimeoutError("slow")
        self._seed()

        response = self.client.post(self._url())

        self.assertEqual(response.status_code, 504)
        self.assertEqual(response.json()["error"]["code"], "AI_TIMEOUT")

    @patch("analyses.ai_service.GeminiPatternAnalyst.analyze")
    def test_rejects_empty_summary(self, analyze):
        analyze.return_value = {"summary": "   "}
        self._seed()

        response = self.client.post(self._url())

        self.assertEqual(response.status_code, 502)

    @patch("analyses.ai_service.GeminiPatternAnalyst.analyze")
    def test_keeps_history_instead_of_overwriting(self, analyze):
        """기록이 늘면 분석이 달라지므로 이력으로 쌓습니다. (§8.10)"""
        analyze.return_value = self.ai_response()
        self._seed()

        self.client.post(self._url())
        self._record(recorded_on=date(2026, 8, 9))
        self.client.post(self._url())

        self.assertEqual(SpendingPatternReport.objects.count(), 2)
        self.assertEqual(
            list(
                SpendingPatternReport.objects.values_list(
                    "record_count", flat=True
                )
            ),
            [4, 3],
        )

    def test_requires_login(self):
        self.client.logout()

        response = self.client.post(self._url())

        self.assertEqual(response.status_code, 403)


class GetPatternReportTests(SpendingPatternTestCase):
    @patch("analyses.ai_service.GeminiPatternAnalyst.analyze")
    def _create(self, analyze, count=3):
        analyze.return_value = self.ai_response()
        self._seed(count=count)
        self.client.post(self._url())

    def test_returns_404_before_first_analysis(self):
        response = self.client.get(self._url())

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "NOT_FOUND")

    def test_returns_latest_report(self):
        self._create()

        response = self.client.get(self._url())

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("만족도가 높고", body["summary"])
        self.assertEqual(body["record_count"], 3)

    def test_fresh_report_is_not_stale(self):
        self._create()

        body = self.client.get(self._url()).json()

        self.assertEqual(body["current_record_count"], 3)
        self.assertFalse(body["is_stale"])

    def test_new_record_makes_report_stale(self):
        """화면이 "다시 분석하기"를 띄울 판단 근거입니다. (§8.10)"""
        self._create()
        self._record(recorded_on=date(2026, 8, 9))

        body = self.client.get(self._url()).json()

        self.assertEqual(body["record_count"], 3)
        self.assertEqual(body["current_record_count"], 4)
        self.assertTrue(body["is_stale"])

    def test_hides_other_users_report(self):
        self._create()
        other = self._create_user("other_user", "other@example.com")
        self.client.force_login(other)

        response = self.client.get(self._url())

        self.assertEqual(response.status_code, 404)


class PurposefulRateTests(SpendingPatternTestCase):
    """목적형 소비 비율 (§8.9). 구매 목적이 "기타"가 아닌 소비입니다."""

    def _stats(self):
        return self.client.get(
            reverse("analyses_api:spending_record_stats")
        ).json()

    def test_counts_records_with_a_specific_purpose(self):
        self._record(purpose=Consideration.Purpose.SELF_DEVELOPMENT)
        self._record(purpose=Consideration.Purpose.TRAVEL)
        self._record(purpose=Consideration.Purpose.ETC)

        body = self._stats()

        self.assertEqual(body["purposeful_count"], 2)
        self.assertEqual(body["purposeful_rate"], 67)
        self.assertEqual(body["purposeful_rate_display"], "67%")

    def test_denominator_is_purchased_records(self):
        """사지 않은 기록은 "소비"가 아니므로 분모에서 빠집니다."""
        self._record(purpose=Consideration.Purpose.WORK)
        self._record(
            purpose=Consideration.Purpose.WORK,
            purchase_status=SpendingRecord.PurchaseStatus.DEFERRED,
        )

        body = self._stats()

        self.assertEqual(body["purchased_count"], 1)
        self.assertEqual(body["purposeful_rate"], 100)

    def test_all_etc_gives_zero(self):
        self._record(purpose=Consideration.Purpose.ETC)

        self.assertEqual(self._stats()["purposeful_rate"], 0)

    def test_no_records_gives_zero_not_error(self):
        body = self._stats()

        self.assertEqual(body["purposeful_count"], 0)
        self.assertEqual(body["purposeful_rate"], 0)
