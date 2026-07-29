from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from core.models import TimeStampedModel


class Category(TimeStampedModel):
    class Code(models.TextChoices):
        TRAVEL = "TRAVEL", "여행"
        HEALTH = "HEALTH", "운동(건강)"
        CULTURE = "CULTURE", "문화(여가)"
        LIVING = "LIVING", "생활편의"
        DIGITAL = "DIGITAL", "디지털 전자기기"
        FINANCE = "FINANCE", "재정"

    code = models.CharField(
        max_length=20,
        choices=Code.choices,
        unique=True,
    )

    name = models.CharField(
        max_length=50,
    )

    emoji = models.CharField(
        max_length=10,
        blank=True,
    )

    display_order = models.PositiveSmallIntegerField(
        default=0,
    )

    is_active = models.BooleanField(
        default=True,
    )

    class Meta:
        ordering = ["display_order", "id"]

    def __str__(self):
        return self.name


class AlternativeItem(TimeStampedModel):
    class CalcType(models.TextChoices):
        UNIT_PRICE = "UNIT_PRICE", "단가 환산"
        SAVINGS = "SAVINGS", "적금"
        DEPOSIT = "DEPOSIT", "예금"
        INVESTMENT = "INVESTMENT", "투자"

    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="alternative_items",
    )

    name = models.CharField(
        max_length=200,
    )

    unit_label = models.CharField(
        max_length=30,
        blank=True,
    )

    average_price = models.PositiveIntegerField()

    spec_note = models.CharField(
        max_length=300,
        blank=True,
    )

    calc_type = models.CharField(
        max_length=20,
        choices=CalcType.choices,
        default=CalcType.UNIT_PRICE,
    )

    calc_params = models.JSONField(
        default=dict,
        blank=True,
    )

    source_name = models.CharField(
        max_length=200,
    )

    source_url = models.URLField(
        max_length=500,
    )

    effective_date = models.DateField()

    is_active = models.BooleanField(
        default=True,
    )

    class Meta:
        ordering = [
            "category__display_order",
            "name",
            "-effective_date",
        ]

        indexes = [
            models.Index(
                fields=["category", "is_active"],
                name="alt_item_category_active_idx",
            ),
        ]

        constraints = [
            models.CheckConstraint(
                condition=Q(average_price__gt=0),
                name="alternative_item_price_gt_0",
            ),
        ]

    def __str__(self):
        return f"{self.category.name} - {self.name}"


class Alternative(TimeStampedModel):
    class ResultType(models.TextChoices):
        QUANTITY = "QUANTITY", "수량 환산"
        FUTURE_VALUE = "FUTURE_VALUE", "미래가치"

    consideration = models.ForeignKey(
        "products.Consideration",
        on_delete=models.CASCADE,
        related_name="alternatives",
    )

    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="alternatives",
    )

    item = models.ForeignKey(
        AlternativeItem,
        on_delete=models.PROTECT,
        related_name="alternatives",
    )

    slot = models.PositiveSmallIntegerField()

    version = models.PositiveIntegerField(
        default=1,
    )

    is_current = models.BooleanField(
        default=True,
    )

    unit_price = models.PositiveIntegerField()

    duration = models.CharField(
        max_length=100,
        blank=True,
    )

    expected_effect = models.TextField(
        blank=True,
    )

    ai_reason = models.TextField(
        blank=True,
    )

    result_type = models.CharField(
        max_length=20,
        choices=ResultType.choices,
    )

    equivalent_quantity = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
    )

    future_value = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    display_text = models.CharField(
        max_length=300,
    )

    class Meta:
        ordering = [
            "category__display_order",
            "slot",
            "-version",
        ]

        constraints = [
            models.CheckConstraint(
                condition=Q(slot__gte=1, slot__lte=3),
                name="alternative_slot_between_1_and_3",
            ),
            models.CheckConstraint(
                condition=Q(version__gte=1),
                name="alternative_version_gte_1",
            ),
            models.CheckConstraint(
                condition=Q(unit_price__gt=0),
                name="alternative_unit_price_gt_0",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        result_type="QUANTITY",
                        equivalent_quantity__isnull=False,
                        future_value__isnull=True,
                    )
                    | Q(
                        result_type="FUTURE_VALUE",
                        equivalent_quantity__isnull=True,
                        future_value__isnull=False,
                    )
                ),
                name="valid_alternative_result",
            ),
            models.UniqueConstraint(
                fields=[
                    "consideration",
                    "category",
                    "slot",
                    "version",
                ],
                name="unique_alternative_slot_version",
            ),
            models.UniqueConstraint(
                fields=[
                    "consideration",
                    "category",
                    "slot",
                ],
                condition=Q(is_current=True),
                name="unique_current_alternative_slot",
            ),
        ]

    def clean(self):
        super().clean()

        if (
            self.item_id is not None
            and self.category_id != self.item.category_id
        ):
            raise ValidationError(
                {
                    "item": (
                        "대안 항목의 카테고리는 "
                        "대안의 카테고리와 같아야 합니다."
                    )
                }
            )

    def __str__(self):
        return (
            f"{self.consideration.product_name} - "
            f"{self.category.name} "
            f"#{self.slot} v{self.version}"
        )


class LLMRequestLog(TimeStampedModel):
    class Purpose(models.TextChoices):
        GENERATE = "GENERATE", "최초 생성"
        REGENERATE = "REGENERATE", "개별 재생성"
        DECISION = "DECISION", "구매 의사결정"

    class Status(models.TextChoices):
        SUCCESS = "SUCCESS", "성공"
        FAILED = "FAILED", "실패"

    consideration = models.ForeignKey(
        "products.Consideration",
        on_delete=models.CASCADE,
        related_name="llm_request_logs",
    )

    purpose = models.CharField(
        max_length=20,
        choices=Purpose.choices,
    )

    model = models.CharField(
        max_length=100,
    )

    prompt = models.TextField()

    response = models.JSONField(
        null=True,
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return (
            f"{self.consideration_id} - "
            f"{self.get_purpose_display()} - "
            f"{self.get_status_display()}"
        )
