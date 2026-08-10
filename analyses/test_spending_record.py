from datetime import date

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from products.models import Consideration

from .models import Decision, FinalChoice, SpendingRecord


class SpendingRecordModelTests(TestCase):
    def setUp(self):
        self.user = self._create_user("record_user", "record@example.com")
        self.consideration = Consideration.objects.create(
            user=self.user,
            product_name="맥북 프로",
            product_price=2_200_000,
            purpose=Consideration.Purpose.WORK,
        )
        self.decision = Decision.objects.create(
            consideration=self.consideration,
            purpose_fit=Decision.Level.HIGH,
            expected_satisfaction=Decision.Level.HIGH,
            recommendation=Decision.Level.MIDDLE,
            key_points=["목적에 적합", "예산 확인 필요", "대안 비교 완료"],
            summary="업무 목적에는 적합하지만 예산을 확인해야 합니다.",
            ai_model="gemini-2.5-flash",
        )
        self.final_choice = FinalChoice.objects.create(
            consideration=self.consideration,
            choice_type=FinalChoice.ChoiceType.PRODUCT,
            decided_on=date(2026, 8, 10),
        )

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
            monthly_budget="300K_500K",
        )

    def _record(self, **overrides):
        values = {
            "user": self.user,
            "consideration": self.consideration,
            "final_choice": self.final_choice,
            "purchase_status": SpendingRecord.PurchaseStatus.PURCHASED,
            "recorded_on": date(2026, 8, 10),
            "purchased_on": date(2026, 8, 10),
            "satisfaction": 4,
            "category": "디지털·전자기기",
            "product_name": "맥북 프로",
            "product_price": 2_200_000,
            "product_url": "https://example.com/macbook",
        }
        values.update(overrides)
        return SpendingRecord(**values)

    def test_purchased_record_connects_existing_analysis(self):
        record = self._record()

        record.full_clean()
        record.save()

        self.assertEqual(
            record.consideration.decision,
            self.decision,
        )

    def test_saves_historical_input_snapshots(self):
        self.consideration.purpose_detail = "업무용 개발 장비"
        self.consideration.compare_criteria = [
            Consideration.CompareCriterion.PRICE,
            Consideration.CompareCriterion.DURATION,
        ]
        self.consideration.save()
        record = self._record(budget_amount_snapshot=2_000_000)

        record.save()

        self.assertEqual(record.purpose_snapshot, Consideration.Purpose.WORK)
        self.assertEqual(record.purpose_detail_snapshot, "업무용 개발 장비")
        self.assertEqual(
            record.compare_criteria_snapshot,
            [
                Consideration.CompareCriterion.PRICE,
                Consideration.CompareCriterion.DURATION,
            ],
        )
        self.assertEqual(record.monthly_budget_snapshot, "300K_500K")
        self.assertEqual(record.budget_amount_snapshot, 2_000_000)

    def test_snapshots_do_not_change_with_original_data(self):
        record = self._record()
        record.save()

        self.consideration.purpose = Consideration.Purpose.TRAVEL
        self.consideration.save()
        self.user.monthly_budget = "OVER_2M"
        self.user.save()
        record.refresh_from_db()

        self.assertEqual(record.purpose_snapshot, Consideration.Purpose.WORK)
        self.assertEqual(record.monthly_budget_snapshot, "300K_500K")

    def test_purchase_requires_date_and_satisfaction(self):
        record = self._record(purchased_on=None, satisfaction=None)

        with self.assertRaises(ValidationError) as context:
            record.full_clean()

        self.assertIn("purchased_on", context.exception.message_dict)
        self.assertIn("satisfaction", context.exception.message_dict)

    def test_non_purchase_rejects_purchase_fields(self):
        record = self._record(
            purchase_status=SpendingRecord.PurchaseStatus.NOT_PURCHASED,
        )

        with self.assertRaises(ValidationError) as context:
            record.full_clean()

        self.assertIn("purchase_status", context.exception.message_dict)

    def test_deferred_record_accepts_empty_purchase_fields(self):
        record = self._record(
            purchase_status=SpendingRecord.PurchaseStatus.DEFERRED,
            purchased_on=None,
            satisfaction=None,
        )

        record.full_clean()

    def test_rejects_another_users_consideration(self):
        other_user = self._create_user("other_user", "other@example.com")
        record = self._record(user=other_user)

        with self.assertRaises(ValidationError) as context:
            record.full_clean()

        self.assertIn("consideration", context.exception.message_dict)

    def test_rejects_final_choice_from_another_consideration(self):
        other_consideration = Consideration.objects.create(
            user=self.user,
            product_name="다른 상품",
            product_price=100_000,
            purpose=Consideration.Purpose.GIFT,
        )
        other_choice = FinalChoice.objects.create(
            consideration=other_consideration,
            choice_type=FinalChoice.ChoiceType.PRODUCT,
            decided_on=date(2026, 8, 10),
        )
        record = self._record(final_choice=other_choice)

        with self.assertRaises(ValidationError) as context:
            record.full_clean()

        self.assertIn("final_choice", context.exception.message_dict)

    def test_database_rejects_satisfaction_outside_range(self):
        record = self._record(satisfaction=6)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                record.save()

    def test_database_rejects_non_purchase_with_purchase_date(self):
        record = self._record(
            purchase_status=SpendingRecord.PurchaseStatus.NOT_PURCHASED,
            satisfaction=None,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                record.save()
