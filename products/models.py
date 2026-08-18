from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.db.models import Q

from core.models import TimeStampedModel


class Consideration(TimeStampedModel):
    class Purpose(models.TextChoices):
        SELF_DEVELOPMENT = "SELF_DEVELOPMENT", "자기계발"
        TRAVEL = "TRAVEL", "여행"
        DESIGN = "DESIGN", "디자인"
        GIFT = "GIFT", "선물"
        WORK = "WORK", "업무"
        HOBBY = "HOBBY", "취미·여가"
        CONVENIENCE = "CONVENIENCE", "일상 편의"
        ETC = "ETC", "기타"

    class CompareCriterion(models.TextChoices):
        PRICE = "PRICE", "가격"
        DURATION = "DURATION", "지속 가능 기간"
        EXPECTED_EFFECT = "EXPECTED_EFFECT", "기대 효과"
        AVAILABLE_BUDGET = "AVAILABLE_BUDGET", "가용 예산"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "작성 중"
        GENERATED = "GENERATED", "대안 생성 완료"
        DECIDED = "DECIDED", "선택 완료"
        CLOSED = "CLOSED", "종료"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="considerations",
    )

    product_name = models.CharField(
        max_length=200,
    )

    product_price = models.PositiveIntegerField()

    product_features = models.TextField(
        blank=True,
    )

    product_duration = models.CharField(
        max_length=100,
        blank=True,
    )

    product_expected_effect = models.TextField(
        blank=True,
    )

    product_url = models.URLField(
        max_length=500,
        blank=True,
    )

    image_url = models.URLField(
        max_length=500,
        blank=True,
    )

    purpose = models.CharField(
        max_length=30,
        choices=Purpose.choices,
    )

    purpose_detail = models.CharField(
        max_length=200,
        blank=True,
    )

    exclude_category = models.ForeignKey(
        "alternatives.Category",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="excluded_considerations",
    )

    compare_criteria = ArrayField(
        base_field=models.CharField(
            max_length=30,
            choices=CompareCriterion.choices,
        ),
        default=list,
        blank=True,
    )

    categories = models.ManyToManyField(
        "alternatives.Category",
        related_name="considerations",
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )

    class Meta:
        ordering = ["-created_at"]

        constraints = [
            models.CheckConstraint(
                condition=Q(product_price__gt=0),
                name="consideration_product_price_gt_0",
            ),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.product_name}"