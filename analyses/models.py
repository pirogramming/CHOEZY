from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

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
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="spending_records",
    )

    final_choice = models.OneToOneField(
        FinalChoice,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="spending_record",
    )

    spent_on = models.DateField()

    category = models.CharField(
        max_length=50,
    )

    item_name = models.CharField(
        max_length=200,
    )

    amount = models.PositiveIntegerField()

    class Meta:
        ordering = ["-spent_on", "-created_at"]

        indexes = [
            models.Index(
                fields=["user", "spent_on"],
                name="spending_user_date_idx",
            ),
        ]

        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0),
                name="spending_amount_gt_0",
            ),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.item_name}"
