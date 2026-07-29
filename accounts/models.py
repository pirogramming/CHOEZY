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
        EXPERIENCE = "EXPERIENCE", "경험·만족 중시"
        VALUE = "VALUE", "가성비 중시"
        GROWTH = "GROWTH", "성장·자기개발 중시"
        ASSET = "ASSET", "자산 형성 중심"

    class ValueCriterion(models.TextChoices):
        PRICE = "PRICE", "가격"
        SATISFACTION = "SATISFACTION", "만족도"
        QUALITY = "QUALITY", "품질"
        UTILIZATION = "UTILIZATION", "활용도"
        LONG_TERM_VALUE = "LONG_TERM_VALUE", "장기 가치"

    class MonthlyBudget(models.TextChoices):
        UNDER_100K = "UNDER_100K", "10만원 이하"
        FROM_100K_TO_300K = "100K_300K", "10~30만원"
        FROM_300K_TO_500K = "300K_500K", "30~50만원"
        FROM_500K_TO_1M = "500K_1M", "50~100만원"
        FROM_1M_TO_2M = "1M_2M", "100~200만원"
        OVER_2M = "OVER_2M", "200만원 이상"

    name = models.CharField(max_length=50)

    birth_date = models.DateField(
        null=True,
        blank=True,
    )

    gender = models.CharField(
        max_length=10,
        choices=Gender.choices,
        blank=True,
    )

    spending_type = models.CharField(
        max_length=20,
        choices=SpendingType.choices,
        blank=True,
    )

    value_criteria = ArrayField(
        base_field=models.CharField(
            max_length=30,
            choices=ValueCriterion.choices,
        ),
        default=list,
        blank=True,
    )

    monthly_budget = models.CharField(
        max_length=20,
        choices=MonthlyBudget.choices,
        blank=True,
    )

    def __str__(self):
        return self.username