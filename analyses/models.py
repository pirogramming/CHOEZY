from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from core.models import TimeStampedModel


# AI 의사결정 화면의 체크리스트 줄 수 (docs/API.md §8.1)
DECISION_KEY_POINT_COUNT = 3


class Decision(TimeStampedModel):
    class Level(models.TextChoices):
        HIGH = "HIGH", "높음"
        MIDDLE = "MIDDLE", "중간"
        LOW = "LOW", "낮음"

    consideration = models.OneToOneField(
        "products.Consideration",
        on_delete=models.CASCADE,
        related_name="decision",
    )

    purpose_fit = models.CharField(
        max_length=10,
        choices=Level.choices,
    )

    expected_satisfaction = models.CharField(
        max_length=10,
        choices=Level.choices,
    )

    recommendation = models.CharField(
        max_length=10,
        choices=Level.choices,
    )

    key_points = ArrayField(
        base_field=models.CharField(max_length=100),
        default=list,
        blank=True,
    )

    summary = models.TextField()

    ai_model = models.CharField(
        max_length=100,
        blank=True,
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(
                    key_points__len__lte=DECISION_KEY_POINT_COUNT,
                ),
                name="decision_key_points_max_count",
            ),
        ]

    def __str__(self):
        return f"{self.consideration.product_name} - AI 의사결정"


class FinalChoice(TimeStampedModel):
    class ChoiceType(models.TextChoices):
        PRODUCT = "PRODUCT", "상품 구매"
        ALTERNATIVE = "ALTERNATIVE", "대안 선택"
        POSTPONE = "POSTPONE", "보류"

    consideration = models.OneToOneField(
        "products.Consideration",
        on_delete=models.CASCADE,
        related_name="final_choice",
    )

    choice_type = models.CharField(
        max_length=20,
        choices=ChoiceType.choices,
    )

    alternative = models.ForeignKey(
        "alternatives.Alternative",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="final_choices",
    )

    memo = models.TextField(
        blank=True,
    )

    decided_on = models.DateField()

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(
                        choice_type="ALTERNATIVE",
                        alternative__isnull=False,
                    )
                    | Q(
                        choice_type__in=[
                            "PRODUCT",
                            "POSTPONE",
                        ],
                        alternative__isnull=True,
                    )
                ),
                name="valid_final_choice_alternative",
            ),
        ]

    def clean(self):
        super().clean()

        if (
            self.alternative_id is not None
            and self.alternative.consideration_id
            != self.consideration_id
        ):
            raise ValidationError(
                {
                    "alternative": (
                        "선택한 대안은 같은 구매 고민에서 "
                        "생성된 대안이어야 합니다."
                    )
                }
            )

    def __str__(self):
        return (
            f"{self.consideration.product_name} - "
            f"{self.get_choice_type_display()}"
        )


class SpendingRecord(TimeStampedModel):
    class PurchaseStatus(models.TextChoices):
        PURCHASED = "PURCHASED", "구매 확정"
        DEFERRED = "DEFERRED", "구매 보류"
        NOT_PURCHASED = "NOT_PURCHASED", "구매 안 함"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="spending_records",
    )

    consideration = models.OneToOneField(
        "products.Consideration",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="spending_record",
    )

    final_choice = models.OneToOneField(
        FinalChoice,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="spending_record",
    )

    purchase_status = models.CharField(
        max_length=20,
        choices=PurchaseStatus.choices,
        default=PurchaseStatus.PURCHASED,
    )

    recorded_on = models.DateField(
        default=timezone.localdate,
    )

    purchased_on = models.DateField(
        null=True,
        blank=True,
    )

    satisfaction = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
    )

    category = models.CharField(
        max_length=50,
    )

    product_name = models.CharField(
        max_length=200,
    )

    product_price = models.PositiveIntegerField()

    product_url = models.URLField(
        max_length=500,
        blank=True,
    )

    image_url = models.URLField(
        max_length=500,
        blank=True,
    )

    # 소비 기록 생성 당시의 입력값을 보존합니다. 원본 고민이나 회원
    # 프로필이 나중에 수정되더라도 과거 기록의 내용은 바뀌지 않습니다.
    purpose_snapshot = models.CharField(
        max_length=30,
        blank=True,
    )

    purpose_detail_snapshot = models.CharField(
        max_length=200,
        blank=True,
    )

    compare_criteria_snapshot = ArrayField(
        base_field=models.CharField(max_length=30),
        default=list,
        blank=True,
    )

    monthly_budget_snapshot = models.CharField(
        max_length=20,
        blank=True,
    )

    budget_amount_snapshot = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-recorded_on", "-created_at"]

        indexes = [
            models.Index(
                fields=["user", "recorded_on"],
                name="spending_user_date_idx",
            ),
            models.Index(
                fields=["user", "purchase_status"],
                name="spending_user_status_idx",
            ),
        ]

        constraints = [
            models.CheckConstraint(
                condition=Q(product_price__gt=0),
                name="spending_product_price_gt_0",
            ),
            models.CheckConstraint(
                condition=(
                    Q(budget_amount_snapshot__isnull=True)
                    | Q(budget_amount_snapshot__gt=0)
                ),
                name="spending_budget_snapshot_gt_0",
            ),
            models.CheckConstraint(
                condition=(
                    Q(satisfaction__isnull=True)
                    | Q(satisfaction__range=(1, 5))
                ),
                name="spending_satisfaction_1_to_5",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        purchase_status="PURCHASED",
                        purchased_on__isnull=False,
                    )
                    | Q(
                        purchase_status__in=[
                            "DEFERRED",
                            "NOT_PURCHASED",
                        ],
                        purchased_on__isnull=True,
                        satisfaction__isnull=True,
                    )
                ),
                name="spending_status_fields_consistent",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}

        if self.consideration_id is None:
            errors["consideration"] = (
                "소비 기록에 구매 고민 연결이 필요합니다."
            )

        if self.purchase_status == self.PurchaseStatus.PURCHASED:
            if self.purchased_on is None:
                errors["purchased_on"] = (
                    "구매 확정 시 구매일이 필요합니다."
                )
            if self.satisfaction is None:
                errors["satisfaction"] = (
                    "구매 확정 시 만족도가 필요합니다."
                )
        elif self.purchased_on is not None or self.satisfaction is not None:
            errors["purchase_status"] = (
                "구매 보류 또는 구매 안 함에는 구매일과 만족도를 "
                "저장할 수 없습니다."
            )

        if (
            self.user_id is not None
            and self.consideration_id is not None
            and self.consideration.user_id != self.user_id
        ):
            errors["consideration"] = (
                "소비 기록과 구매 고민의 사용자가 일치해야 합니다."
            )

        if self.final_choice_id is not None and (
            self.consideration_id
            != self.final_choice.consideration_id
        ):
            errors["final_choice"] = (
                "소비 기록과 최종 선택은 같은 구매 고민에 속해야 합니다."
            )

        if errors:
            raise ValidationError(errors)

    def capture_snapshots(self):
        """아직 비어 있는 당시 입력값을 연결 객체에서 복사합니다."""
        if self.consideration_id is not None:
            consideration = self.consideration
            if not self.purpose_snapshot:
                self.purpose_snapshot = consideration.purpose
            if not self.purpose_detail_snapshot:
                self.purpose_detail_snapshot = consideration.purpose_detail
            if not self.compare_criteria_snapshot:
                self.compare_criteria_snapshot = list(
                    consideration.compare_criteria
                )

        if self.user_id is not None and not self.monthly_budget_snapshot:
            self.monthly_budget_snapshot = self.user.monthly_budget

    def save(self, *args, **kwargs):
        self.capture_snapshots()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username} - {self.product_name}"
