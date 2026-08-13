"""소비 기록 통계 API 테스트 (docs/API.md §8.9)."""

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from alternatives.models import Category
from products.models import Consideration

from .models import SpendingRecord


class SpendingStatsTestCase(TestCase):
    def setUp(self):
        self.user = self._create_user("stats_user", "stats@example.com")
        self.client.force_login(self.user)

    def _create_user(self, username, email):
        return get_user_model().objects.create_user(
            username=username,
            email=email,
            password="StrongPass!2468",
            name="테스트 사용자",
            birth_date=date(2000, 1, 1),
            gender="FEMALE",
            spending_type=["VALUE"],
            value_criteria=["PRICE"],
            monthly_budget="OVER_2M",
        )

    def _record(
        self,
        price,
        category,
        recorded_on,
        purchase_status=SpendingRecord.PurchaseStatus.PURCHASED,
        satisfaction=None,
        purpose=Consideration.Purpose.SELF_DEVELOPMENT,
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
        return SpendingRecord.objects.create(
            user=owner,
            consideration=consideration,
            purchase_status=purchase_status,
            recorded_on=recorded_on,
            purchased_on=recorded_on if purchased else None,
            satisfaction=satisfaction if purchased else None,
            category=category,
            product_name=consideration.product_name,
            product_price=price,
        )

    def _url(self):
        return reverse("analyses_api:spending_record_stats")

    def _get(self, **params):
        return self.client.get(self._url(), params).json()


class EmptyStatsTests(SpendingStatsTestCase):
    """신규 가입자는 기록이 0건입니다. 0으로 나누면 500이 납니다. (§8.9)"""

    def test_zero_records_returns_zeroes_not_error(self):
        response = self.client.get(self._url())

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["total_count"], 0)
        self.assertEqual(body["total_spent"], 0)
        self.assertEqual(body["purchase_rate"], 0)

    def test_zero_records_renders_dash_and_null(self):
        body = self._get()

        self.assertIsNone(body["average_satisfaction"])
        self.assertEqual(body["average_satisfaction_display"], "—")
        self.assertIsNone(body["top_category"])
        self.assertIsNone(body["highest_satisfaction_purpose"])
        self.assertIsNone(body["lowest_satisfaction_purpose"])
        self.assertEqual(body["by_category"], [])
        self.assertEqual(body["chart"]["slices"], [])

    def test_month_with_no_records_is_not_an_error(self):
        self._record(100_000, "여행", date(2026, 7, 1), satisfaction=4)

        body = self._get(month="2026-08")

        self.assertEqual(body["total_count"], 0)
        self.assertEqual(body["total_spent"], 0)


class StatsCalculationTests(SpendingStatsTestCase):
    def setUp(self):
        super().setUp()
        # 8월: 구매 확정 2건(합 3,000,000) + 보류 1건 + 안 함 1건
        self._record(
            2_000_000, "디지털·전자기기", date(2026, 8, 3), satisfaction=5
        )
        self._record(1_000_000, "여행", date(2026, 8, 10), satisfaction=2)
        self._record(
            500_000,
            "여행",
            date(2026, 8, 15),
            purchase_status=SpendingRecord.PurchaseStatus.DEFERRED,
        )
        self._record(
            300_000,
            "운동·건강",
            date(2026, 8, 20),
            purchase_status=SpendingRecord.PurchaseStatus.NOT_PURCHASED,
        )

    def test_total_spent_counts_purchased_only(self):
        """사지 않은 물건 값을 소비 금액에 더하면 안 됩니다. (§8.9)"""
        body = self._get(month="2026-08")

        self.assertEqual(body["total_spent"], 3_000_000)
        self.assertEqual(body["total_spent_display"], "3,000,000원")
        self.assertEqual(body["purchased_count"], 2)

    def test_purchase_rate_denominator_is_all_records(self):
        body = self._get(month="2026-08")

        self.assertEqual(body["total_count"], 4)
        self.assertEqual(body["purchase_rate"], 50)
        self.assertEqual(body["purchase_rate_display"], "50%")

    def test_average_satisfaction_is_rounded_to_one_decimal(self):
        body = self._get(month="2026-08")

        self.assertEqual(body["average_satisfaction"], 3.5)
        self.assertEqual(body["average_satisfaction_display"], "3.5점")

    def test_category_breakdown_is_sorted_by_amount(self):
        body = self._get(month="2026-08")

        names = [row["name"] for row in body["by_category"]]
        self.assertEqual(names, ["디지털·전자기기", "여행"])
        self.assertEqual(body["by_category"][0]["amount"], 2_000_000)
        self.assertEqual(body["by_category"][0]["ratio"], 67)
        self.assertEqual(body["by_category"][0]["ratio_display"], "67%")

    def test_category_breakdown_excludes_non_purchased(self):
        """보류·안 함 분야는 소비 금액이 없으므로 빠집니다."""
        body = self._get(month="2026-08")

        names = [row["name"] for row in body["by_category"]]
        self.assertNotIn("운동·건강", names)

    def test_top_category_is_the_largest_amount(self):
        body = self._get(month="2026-08")

        self.assertEqual(body["top_category"]["name"], "디지털·전자기기")
        self.assertEqual(body["top_category"]["code"], "DIGITAL")

    def test_category_code_comes_from_master(self):
        body = self._get(month="2026-08")

        codes = {row["name"]: row["code"] for row in body["by_category"]}
        self.assertEqual(codes["여행"], "TRAVEL")

    def test_unknown_category_name_has_null_code(self):
        self._record(
            100_000, "예전 이름", date(2026, 8, 25), satisfaction=3
        )

        body = self._get(month="2026-08")

        codes = {row["name"]: row["code"] for row in body["by_category"]}
        self.assertIsNone(codes["예전 이름"])

    def test_low_satisfaction_counts_three_and_below(self):
        body = self._get(month="2026-08")

        self.assertEqual(body["low_satisfaction"]["threshold"], 3)
        self.assertEqual(body["low_satisfaction"]["count"], 1)
        self.assertEqual(body["low_satisfaction"]["amount"], 1_000_000)
        self.assertEqual(
            body["low_satisfaction"]["amount_display"], "1,000,000원"
        )


class PurposeStatsTests(SpendingStatsTestCase):
    def setUp(self):
        super().setUp()
        self._record(
            1_000_000,
            "디지털·전자기기",
            date(2026, 8, 1),
            satisfaction=5,
            purpose=Consideration.Purpose.SELF_DEVELOPMENT,
        )
        self._record(
            500_000,
            "디지털·전자기기",
            date(2026, 8, 2),
            satisfaction=4,
            purpose=Consideration.Purpose.SELF_DEVELOPMENT,
        )
        self._record(
            200_000,
            "생활·편의",
            date(2026, 8, 3),
            satisfaction=2,
            purpose=Consideration.Purpose.CONVENIENCE,
        )

    def test_average_satisfaction_per_purpose(self):
        body = self._get(month="2026-08")

        rows = {row["purpose"]: row for row in body["by_purpose"]}
        self.assertEqual(rows["SELF_DEVELOPMENT"]["average_satisfaction"], 4.5)
        self.assertEqual(rows["SELF_DEVELOPMENT"]["count"], 2)
        self.assertEqual(rows["SELF_DEVELOPMENT"]["purpose_display"], "자기계발")

    def test_highest_and_lowest_purpose(self):
        """리포트의 "만족도 높은 소비"·"다시 생각해볼 소비" 카드입니다."""
        body = self._get(month="2026-08")

        self.assertEqual(
            body["highest_satisfaction_purpose"]["purpose"],
            "SELF_DEVELOPMENT",
        )
        self.assertEqual(
            body["highest_satisfaction_purpose"][
                "average_satisfaction_display"
            ],
            "4.5점",
        )
        self.assertEqual(
            body["lowest_satisfaction_purpose"]["purpose"], "CONVENIENCE"
        )
        self.assertEqual(
            body["lowest_satisfaction_purpose"]["purpose_display"],
            "일상 편의",
        )

    def test_purpose_stats_ignore_records_without_satisfaction(self):
        self._record(
            900_000,
            "여행",
            date(2026, 8, 4),
            purchase_status=SpendingRecord.PurchaseStatus.DEFERRED,
            purpose=Consideration.Purpose.TRAVEL,
        )

        body = self._get(month="2026-08")

        purposes = [row["purpose"] for row in body["by_purpose"]]
        self.assertNotIn("TRAVEL", purposes)


class DonutChartTests(SpendingStatsTestCase):
    def _spread(self, amounts):
        names = [
            "디지털·전자기기",
            "여행",
            "문화·여가",
            "생활·편의",
            "운동·건강",
            "재정",
        ]
        for index, amount in enumerate(amounts):
            self._record(
                amount, names[index], date(2026, 8, index + 1), satisfaction=4
            )

    def test_three_or_fewer_categories_have_no_others_slice(self):
        self._spread([300_000, 200_000, 100_000])

        slices = self._get(month="2026-08")["chart"]["slices"]

        self.assertEqual(len(slices), 3)
        self.assertFalse(any(row["is_others"] for row in slices))

    def test_more_than_three_categories_collapse_into_others(self):
        self._spread([500_000, 300_000, 100_000, 60_000, 40_000])

        slices = self._get(month="2026-08")["chart"]["slices"]

        self.assertEqual(len(slices), 4)
        others = slices[-1]
        self.assertTrue(others["is_others"])
        self.assertEqual(others["name"], "기타")
        self.assertIsNone(others["code"])

    def test_others_slice_carries_detail_items(self):
        """"기타 영역을 클릭하면 세부 영역을 확인할 수 있어요" 화면입니다."""
        self._spread([500_000, 300_000, 100_000, 60_000, 40_000])

        others = self._get(month="2026-08")["chart"]["slices"][-1]

        names = [item["name"] for item in others["items"]]
        self.assertEqual(names, ["생활·편의", "운동·건강"])

    def test_slice_ratios_always_total_100(self):
        """반올림 때문에 도넛이 비거나 넘치면 안 됩니다. (§8.9)"""
        self._spread([100_000, 100_000, 100_000])

        slices = self._get(month="2026-08")["chart"]["slices"]

        self.assertEqual(sum(row["ratio"] for row in slices), 100)

    def test_category_ratios_total_100_with_awkward_rounding(self):
        # 6등분은 16.67%라 그대로 반올림하면 17×6 = 102가 됩니다.
        self._spread([100_000] * 6)

        body = self._get(month="2026-08")

        self.assertEqual(
            sum(row["ratio"] for row in body["by_category"]), 100
        )
        self.assertEqual(
            sum(row["ratio"] for row in body["chart"]["slices"]), 100
        )


class StatsPeriodTests(SpendingStatsTestCase):
    def setUp(self):
        super().setUp()
        self._record(
            1_000_000, "여행", date(2026, 7, 31), satisfaction=5
        )
        self._record(
            2_000_000, "여행", date(2026, 8, 1), satisfaction=3
        )
        self._record(
            3_000_000, "여행", date(2026, 8, 31), satisfaction=1
        )

    def test_month_filter_uses_inclusive_bounds(self):
        body = self._get(month="2026-08")

        self.assertEqual(body["total_count"], 2)
        self.assertEqual(body["total_spent"], 5_000_000)

    def test_period_describes_the_month(self):
        body = self._get(month="2026-08")

        self.assertEqual(body["period"]["month"], "2026-08")
        self.assertEqual(body["period"]["label"], "2026년 8월")
        self.assertEqual(body["period"]["date_from"], "2026-08-01")
        self.assertEqual(body["period"]["date_to"], "2026-08-31")

    def test_february_end_of_month_is_correct(self):
        self._record(500_000, "여행", date(2026, 2, 28), satisfaction=4)

        body = self._get(month="2026-02")

        self.assertEqual(body["period"]["date_to"], "2026-02-28")
        self.assertEqual(body["total_count"], 1)

    def test_omitting_month_covers_all_records(self):
        body = self._get()

        self.assertEqual(body["total_count"], 3)
        self.assertEqual(body["total_spent"], 6_000_000)
        self.assertIsNone(body["period"]["month"])
        self.assertEqual(body["period"]["label"], "전체 기간")

    def test_rejects_malformed_month(self):
        response = self.client.get(self._url(), {"month": "2026-13"})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["error"]["code"], "VALIDATION_ERROR"
        )

    def test_rejects_non_month_string(self):
        response = self.client.get(self._url(), {"month": "8월"})

        self.assertEqual(response.status_code, 400)


class StatsIsolationTests(SpendingStatsTestCase):
    def test_other_users_records_are_excluded(self):
        other = self._create_user("other_user", "other@example.com")
        self._record(
            9_000_000, "여행", date(2026, 8, 1), satisfaction=5, user=other
        )
        self._record(1_000_000, "여행", date(2026, 8, 1), satisfaction=4)

        body = self._get(month="2026-08")

        self.assertEqual(body["total_count"], 1)
        self.assertEqual(body["total_spent"], 1_000_000)

    def test_requires_login(self):
        self.client.logout()

        response = self.client.get(self._url())

        self.assertEqual(response.status_code, 403)
