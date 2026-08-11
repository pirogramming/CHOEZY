from django.contrib.auth.models import AbstractUser
from django.contrib.postgres.fields import ArrayField
from django.db import models

from core.models import TimeStampedModel


class User(AbstractUser, TimeStampedModel):
    class Gender(models.TextChoices):
        FEMALE = "FEMALE", "여성"
        MALE = "MALE", "남성"
        OTHER = "OTHER", "기타"

    class SpendingType(models.TextChoices):
        VALUE = "VALUE", "가성비 중시"
        QUALITY = "QUALITY", "품질 중시"
        EXPERIENCE = "EXPERIENCE", "경험·만족 중시"
        GROWTH = "GROWTH", "자기계발 중시"
        ASSET = "ASSET", "자산 형성 중시"
        CAUTIOUS = "CAUTIOUS", "신중한 소비 중시"

    class ValueCriterion(models.TextChoices):
        PRICE = "PRICE", "가격"
        SATISFACTION = "SATISFACTION", "만족감"
        QUALITY = "QUALITY", "품질·성능"
        UTILIZATION = "UTILIZATION", "활용도"
        DURATION = "DURATION", "지속·유지 기간"
        EFFICIENCY = "EFFICIENCY", "효율성"

    class MonthlyBudget(models.TextChoices):
        UNDER_100K = "UNDER_100K", "10만원 이하"
        FROM_100K_TO_300K = "100K_300K", "10~30만원"
        FROM_300K_TO_500K = "300K_500K", "30~50만원"
        FROM_500K_TO_1M = "500K_1M", "50~100만원"
        FROM_1M_TO_2M = "1M_2M", "100~200만원"
        OVER_2M = "OVER_2M", "200만원 이상"

    email = models.EmailField(
        unique=True,
    )

    name = models.CharField(
        max_length=50,
    )

    birth_date = models.DateField()

    gender = models.CharField(
        max_length=10,
        choices=Gender.choices,
    )

    spending_type = ArrayField(
        base_field=models.CharField(
            max_length=20,
            choices=SpendingType.choices,
        ),
        default=list,
    )

    value_criteria = ArrayField(
        base_field=models.CharField(
            max_length=30,
            choices=ValueCriterion.choices,
        ),
        default=list,
    )

    monthly_budget = models.CharField(
        max_length=20,
        choices=MonthlyBudget.choices,
    )

    class Meta(AbstractUser.Meta):
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(name=""),
                name="user_name_not_empty",
            ),
            models.CheckConstraint(
                condition=~models.Q(email=""),
                name="user_email_not_empty",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    gender__in=["FEMALE", "MALE", "OTHER"],
                ),
                name="user_valid_gender",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(spending_type__len__gte=1)
                    & models.Q(spending_type__len__lte=2)
                    & models.Q(
                        spending_type__contained_by=[
                            "VALUE",
                            "QUALITY",
                            "EXPERIENCE",
                            "GROWTH",
                            "ASSET",
                            "CAUTIOUS",
                        ],
                    )
                ),
                name="user_valid_spending_types",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(value_criteria__len__gte=1)
                    & models.Q(value_criteria__len__lte=3)
                    & models.Q(
                        value_criteria__contained_by=[
                            "PRICE",
                            "SATISFACTION",
                            "QUALITY",
                            "UTILIZATION",
                            "DURATION",
                            "EFFICIENCY",
                        ],
                    )
                ),
                name="user_valid_value_criteria",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    monthly_budget__in=[
                        "UNDER_100K",
                        "100K_300K",
                        "300K_500K",
                        "500K_1M",
                        "1M_2M",
                        "OVER_2M",
                    ],
                ),
                name="user_valid_monthly_budget",
            ),
        ]

    def __str__(self):
        return self.username


# 월 소비 예산 구간 → (하한, 상한). 상한 None은 "이상"입니다.
# 비교표의 "가용 예산" 열(docs/API.md §6.5)과 소비 기록의 당시 예산
# 스냅샷(§8.4)이 같은 값을 써야 화면끼리 숫자가 어긋나지 않으므로
# 구간 정의는 여기 한 곳에만 둡니다.
MONTHLY_BUDGET_RANGES = {
    User.MonthlyBudget.UNDER_100K: (0, 100_000),
    User.MonthlyBudget.FROM_100K_TO_300K: (100_000, 300_000),
    User.MonthlyBudget.FROM_300K_TO_500K: (300_000, 500_000),
    User.MonthlyBudget.FROM_500K_TO_1M: (500_000, 1_000_000),
    User.MonthlyBudget.FROM_1M_TO_2M: (1_000_000, 2_000_000),
    User.MonthlyBudget.OVER_2M: (2_000_000, None),
}
