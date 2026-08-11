"""소비 기록 API 테스트 (docs/API.md §8.5~§8.8)."""

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from alternatives.models import Category
from products.models import Consideration

from .models import Decision, SpendingRecord


class SpendingRecordAPITestCase(TestCase):
    def setUp(self):
        self.user = self._create_user("record_user", "record@example.com")
        # 카테고리 6개는 마이그레이션 시드로 이미 들어 있습니다.
        self.category = Category.objects.get(code=Category.Code.DIGITAL)
        self.consideration = self._create_consideration()
        self.client.force_login(self.user)

    def _create_user(self, username, email, monthly_budget="OVER_2M"):
        return get_user_model().objects.create_user(
            username=username,
            email=email,
            password="StrongPass!2468",
            name="테스트 사용자",
            birth_date=date(2000, 1, 1),
            gender="FEMALE",
            spending_type=["VALUE"],
            value_criteria=["PRICE"],
            monthly_budget=monthly_budget,
        )

    def _create_consideration(self, user=None, **overrides):
        values = {
            "user": user or self.user,
            "product_name": "MacBook Air",
            "product_price": 2_200_000,
            "product_url": "https://example.com/macbook-air",
            "purpose": Consideration.Purpose.SELF_DEVELOPMENT,
            "purpose_detail": "공부용 개발 장비",
            "compare_criteria": [
                Consideration.CompareCriterion.PRICE,
                Consideration.CompareCriterion.DURATION,
            ],
            "exclude_category": self.category,
            "status": Consideration.Status.GENERATED,
        }
        values.update(overrides)
        return Consideration.objects.create(**values)

    def _detail_url(self, consideration=None):
        return reverse(
            "analyses_api:spending_record",
            args=[(consideration or self.consideration).pk],
        )

    def _list_url(self):
        return reverse("analyses_api:spending_record_list")

    def _post(self, payload, consideration=None):
        return self.client.post(
            self._detail_url(consideration),
            payload,
            content_type="application/json",
        )

    def _patch(self, payload, consideration=None):
        return self.client.patch(
            self._detail_url(consideration),
            payload,
            content_type="application/json",
        )


class CreateSpendingRecordTests(SpendingRecordAPITestCase):
    def test_creates_purchased_record_from_two_fields(self):
        response = self._post({"purchase_status": "PURCHASED",
                               "satisfaction": 4})

        self.assertEqual(response.status_code, 201)
        record = SpendingRecord.objects.get()
        self.assertEqual(record.user, self.user)
        self.assertEqual(record.consideration, self.consideration)
        self.assertEqual(record.satisfaction, 4)

    def test_server_fills_purchase_date_without_input(self):
        """구매 확정 팝업에는 날짜 입력란이 없습니다. (§8.4)"""
        self._post({"purchase_status": "PURCHASED", "satisfaction": 5})

        record = SpendingRecord.objects.get()
        self.assertEqual(record.purchased_on, timezone.localdate())
        self.assertEqual(record.recorded_on, timezone.localdate())

    def test_server_fills_snapshots_from_consideration(self):
        self._post({"purchase_status": "PURCHASED", "satisfaction": 3})

        record = SpendingRecord.objects.get()
        self.assertEqual(record.product_name, "MacBook Air")
        self.assertEqual(record.product_price, 2_200_000)
        self.assertEqual(record.category, "디지털·전자기기")
        self.assertEqual(
            record.purpose_snapshot,
            Consideration.Purpose.SELF_DEVELOPMENT,
        )
        self.assertEqual(record.purpose_detail_snapshot, "공부용 개발 장비")
        self.assertEqual(record.monthly_budget_snapshot, "OVER_2M")
        # "200만원 이상" 구간의 하한
        self.assertEqual(record.budget_amount_snapshot, 2_000_000)

    def test_lowest_budget_bracket_uses_upper_bound(self):
        """하한이 0이면 `budget_amount_snapshot > 0` 제약에 걸립니다."""
        user = self._create_user(
            "small_budget", "small@example.com", monthly_budget="UNDER_100K"
        )
        consideration = self._create_consideration(user=user)
        self.client.force_login(user)

        response = self._post(
            {"purchase_status": "PURCHASED", "satisfaction": 3},
            consideration=consideration,
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            SpendingRecord.objects.get().budget_amount_snapshot, 100_000
        )

    def test_falls_back_to_etc_when_product_category_missing(self):
        consideration = self._create_consideration(exclude_category=None)

        response = self._post(
            {"purchase_status": "NOT_PURCHASED"}, consideration=consideration
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            SpendingRecord.objects.get(consideration=consideration).category,
            "기타",
        )

    def test_creation_moves_consideration_to_decided(self):
        self._post({"purchase_status": "DEFERRED"})

        self.consideration.refresh_from_db()
        self.assertEqual(
            self.consideration.status, Consideration.Status.DECIDED
        )

    def test_deferred_record_stores_no_purchase_fields(self):
        response = self._post({"purchase_status": "DEFERRED"})

        self.assertEqual(response.status_code, 201)
        record = SpendingRecord.objects.get()
        self.assertIsNone(record.purchased_on)
        self.assertIsNone(record.satisfaction)

    def test_rejects_purchased_without_satisfaction(self):
        response = self._post({"purchase_status": "PURCHASED"})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["error"]["code"], "VALIDATION_ERROR"
        )
        self.assertFalse(SpendingRecord.objects.exists())

    def test_rejects_satisfaction_on_non_purchase(self):
        response = self._post(
            {"purchase_status": "DEFERRED", "satisfaction": 4}
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(SpendingRecord.objects.exists())

    def test_rejects_satisfaction_outside_range(self):
        response = self._post(
            {"purchase_status": "PURCHASED", "satisfaction": 6}
        )

        self.assertEqual(response.status_code, 400)

    def test_rejects_draft_consideration(self):
        consideration = self._create_consideration(
            status=Consideration.Status.DRAFT
        )

        response = self._post(
            {"purchase_status": "DEFERRED"}, consideration=consideration
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "INVALID_STATUS")

    def test_rejects_duplicate_record(self):
        self._post({"purchase_status": "DEFERRED"})

        response = self._post({"purchase_status": "PURCHASED",
                               "satisfaction": 4})

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "ALREADY_EXISTS")

    def test_rejects_another_users_consideration(self):
        other = self._create_user("other_user", "other@example.com")
        consideration = self._create_consideration(user=other)

        response = self._post(
            {"purchase_status": "DEFERRED"}, consideration=consideration
        )

        self.assertEqual(response.status_code, 404)

    def test_requires_login(self):
        self.client.logout()

        response = self._post({"purchase_status": "DEFERRED"})

        self.assertEqual(response.status_code, 403)


class SpendingRecordDetailTests(SpendingRecordAPITestCase):
    def setUp(self):
        super().setUp()
        self._post({"purchase_status": "PURCHASED", "satisfaction": 3})

    def test_detail_matches_popup_layout(self):
        response = self.client.get(self._detail_url())

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["purchase_status_display"], "구매함")
        self.assertEqual(body["product_price_display"], "2,200,000원")
        self.assertEqual(body["purpose_display"], "자기계발")
        self.assertEqual(
            body["compare_criteria_display"], ["가격", "지속 가능 기간"]
        )
        self.assertEqual(body["budget_amount_display"], "2,000,000원")
        self.assertEqual(body["satisfaction_display"], "3점")
        self.assertEqual(
            body["recorded_on_display"],
            timezone.localdate().strftime("%Y.%m.%d"),
        )

    def test_detail_embeds_decision_when_present(self):
        Decision.objects.create(
            consideration=self.consideration,
            purpose_fit=Decision.Level.HIGH,
            expected_satisfaction=Decision.Level.MIDDLE,
            recommendation=Decision.Level.MIDDLE,
            key_points=["목적 적합", "예산 확인", "대안 비교"],
            summary="업무 목적에는 적합합니다.",
            ai_model="gemini-2.5-flash",
        )

        body = self.client.get(self._detail_url()).json()

        self.assertEqual(body["decision"]["purpose_fit"], "HIGH")
        self.assertIn("gauge", body["decision"]["chart"])

    def test_decision_is_null_when_missing(self):
        body = self.client.get(self._detail_url()).json()

        self.assertIsNone(body["decision"])

    def test_empty_values_render_as_dash(self):
        record = SpendingRecord.objects.get()
        record.purchase_status = SpendingRecord.PurchaseStatus.DEFERRED
        record.purchased_on = None
        record.satisfaction = None
        record.save()

        body = self.client.get(self._detail_url()).json()

        self.assertEqual(body["satisfaction_display"], "—")

    def test_missing_record_returns_404(self):
        consideration = self._create_consideration()

        response = self.client.get(self._detail_url(consideration))

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "NOT_FOUND")


class UpdateSpendingRecordTests(SpendingRecordAPITestCase):
    def setUp(self):
        super().setUp()
        self._post({"purchase_status": "PURCHASED", "satisfaction": 3})

    def test_updates_satisfaction(self):
        response = self._patch(
            {"purchase_status": "PURCHASED", "satisfaction": 5}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(SpendingRecord.objects.get().satisfaction, 5)

    def test_switching_away_from_purchased_clears_purchase_fields(self):
        """남겨두면 상태 일관성 제약에 걸려 500이 납니다. (§8.7)"""
        response = self._patch({"purchase_status": "DEFERRED"})

        self.assertEqual(response.status_code, 200)
        record = SpendingRecord.objects.get()
        self.assertIsNone(record.purchased_on)
        self.assertIsNone(record.satisfaction)

    def test_switching_back_to_purchased_refills_date(self):
        self._patch({"purchase_status": "NOT_PURCHASED"})

        response = self._patch(
            {"purchase_status": "PURCHASED", "satisfaction": 2}
        )

        self.assertEqual(response.status_code, 200)
        record = SpendingRecord.objects.get()
        self.assertEqual(record.purchased_on, timezone.localdate())
        self.assertEqual(record.satisfaction, 2)

    def test_does_not_touch_snapshots(self):
        self.consideration.product_name = "바뀐 상품"
        self.consideration.save()

        self._patch({"purchase_status": "PURCHASED", "satisfaction": 1})

        self.assertEqual(
            SpendingRecord.objects.get().product_name, "MacBook Air"
        )

    def test_rejects_purchased_without_satisfaction(self):
        response = self._patch({"purchase_status": "PURCHASED"})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(SpendingRecord.objects.get().satisfaction, 3)

    def test_missing_record_returns_404(self):
        consideration = self._create_consideration()

        response = self._patch(
            {"purchase_status": "DEFERRED"}, consideration=consideration
        )

        self.assertEqual(response.status_code, 404)


class SpendingRecordListTests(SpendingRecordAPITestCase):
    def setUp(self):
        super().setUp()
        self.purchased = self._record(
            recorded_on=date(2026, 6, 3),
            purchase_status=SpendingRecord.PurchaseStatus.PURCHASED,
            purchased_on=date(2026, 6, 3),
            satisfaction=4,
            category="디지털·전자기기",
            purpose=Consideration.Purpose.SELF_DEVELOPMENT,
        )
        self.deferred = self._record(
            recorded_on=date(2026, 7, 10),
            purchase_status=SpendingRecord.PurchaseStatus.DEFERRED,
            category="여행",
            purpose=Consideration.Purpose.TRAVEL,
        )
        self.not_purchased = self._record(
            recorded_on=date(2026, 8, 1),
            purchase_status=SpendingRecord.PurchaseStatus.NOT_PURCHASED,
            category="여행",
            purpose=Consideration.Purpose.TRAVEL,
        )

    def _record(self, purpose, **overrides):
        consideration = self._create_consideration(purpose=purpose)
        return SpendingRecord.objects.create(
            user=self.user,
            consideration=consideration,
            product_name=consideration.product_name,
            product_price=consideration.product_price,
            **overrides,
        )

    def _get(self, **params):
        return self.client.get(self._list_url(), params).json()

    def test_returns_all_records_newest_first(self):
        """필터가 없으면 구매 보류까지 포함한 전체입니다. (§8.8)"""
        body = self._get()

        self.assertEqual(body["count"], 3)
        self.assertEqual(
            [item["id"] for item in body["results"]],
            [self.not_purchased.id, self.deferred.id, self.purchased.id],
        )

    def test_deferred_card_shows_dash_for_satisfaction(self):
        """보류 카드는 만족도가 비어 있어 프론트가 별을 0개 그립니다."""
        body = self._get(purchase_status="DEFERRED")

        card = body["results"][0]
        self.assertEqual(card["purchase_status_display"], "구매 보류")
        self.assertIsNone(card["satisfaction"])
        self.assertEqual(card["satisfaction_display"], "—")

    def test_filters_by_single_status(self):
        body = self._get(purchase_status="PURCHASED")

        self.assertEqual(body["count"], 1)
        self.assertEqual(body["results"][0]["id"], self.purchased.id)

    def test_filters_by_multiple_statuses(self):
        """탭 하나가 상태 여러 개를 묶을 수 있습니다. (§8.8)"""
        body = self._get(purchase_status="DEFERRED,NOT_PURCHASED")

        self.assertEqual(body["count"], 2)

    def test_filters_by_category_and_purpose(self):
        self.assertEqual(self._get(category="여행")["count"], 2)
        self.assertEqual(self._get(purpose="TRAVEL")["count"], 2)

    def test_filters_by_date_range_inclusive(self):
        body = self._get(date_from="2026-06-03", date_to="2026-07-10")

        self.assertEqual(body["count"], 2)

    def test_paginates_with_has_next(self):
        first = self._get(page=1, page_size=2)

        self.assertEqual(first["count"], 3)
        self.assertEqual(len(first["results"]), 2)
        self.assertTrue(first["has_next"])

        second = self._get(page=2, page_size=2)

        self.assertEqual(len(second["results"]), 1)
        self.assertFalse(second["has_next"])

    def test_page_past_the_end_returns_last_page(self):
        body = self._get(page=99, page_size=2)

        self.assertFalse(body["has_next"])

    def test_list_item_omits_decision(self):
        body = self._get()

        self.assertNotIn("decision", body["results"][0])
        self.assertIn("product_price_display", body["results"][0])

    def test_hides_other_users_records(self):
        other = self._create_user("other_user", "other@example.com")
        self.client.force_login(other)

        self.assertEqual(self._get()["count"], 0)

    def test_rejects_unknown_status_value(self):
        response = self.client.get(
            self._list_url(), {"purchase_status": "BOUGHT"}
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["error"]["code"], "VALIDATION_ERROR"
        )
