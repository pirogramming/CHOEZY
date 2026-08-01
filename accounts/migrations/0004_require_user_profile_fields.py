import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0003_alter_user_spending_type_alter_user_value_criteria"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="birth_date",
            field=models.DateField(),
        ),
        migrations.AlterField(
            model_name="user",
            name="gender",
            field=models.CharField(
                choices=[
                    ("FEMALE", "여성"),
                    ("MALE", "남성"),
                    ("OTHER", "기타"),
                ],
                max_length=10,
            ),
        ),
        migrations.AlterField(
            model_name="user",
            name="spending_type",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.CharField(
                    choices=[
                        ("VALUE", "가성비 중시"),
                        ("QUALITY", "품질 중시"),
                        ("EXPERIENCE", "경험·만족 중시"),
                        ("GROWTH", "자기계발 중시"),
                        ("ASSET", "자산 형성 중시"),
                        ("CAUTIOUS", "신중한 소비 중시"),
                    ],
                    max_length=20,
                ),
                default=list,
                size=None,
            ),
        ),
        migrations.AlterField(
            model_name="user",
            name="value_criteria",
            field=django.contrib.postgres.fields.ArrayField(
                base_field=models.CharField(
                    choices=[
                        ("PRICE", "가격"),
                        ("SATISFACTION", "만족감"),
                        ("QUALITY", "품질·성능"),
                        ("UTILIZATION", "활용도"),
                        ("DURATION", "지속·유지 기간"),
                        ("EFFICIENCY", "효율성"),
                    ],
                    max_length=30,
                ),
                default=list,
                size=None,
            ),
        ),
        migrations.AlterField(
            model_name="user",
            name="monthly_budget",
            field=models.CharField(
                choices=[
                    ("UNDER_100K", "10만원 이하"),
                    ("100K_300K", "10~30만원"),
                    ("300K_500K", "30~50만원"),
                    ("500K_1M", "50~100만원"),
                    ("1M_2M", "100~200만원"),
                    ("OVER_2M", "200만원 이상"),
                ],
                max_length=20,
            ),
        ),
        migrations.AddConstraint(
            model_name="user",
            constraint=models.CheckConstraint(
                condition=~models.Q(name=""),
                name="user_name_not_empty",
            ),
        ),
        migrations.AddConstraint(
            model_name="user",
            constraint=models.CheckConstraint(
                condition=~models.Q(email=""),
                name="user_email_not_empty",
            ),
        ),
        migrations.AddConstraint(
            model_name="user",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    gender__in=["FEMALE", "MALE", "OTHER"],
                ),
                name="user_valid_gender",
            ),
        ),
        migrations.AddConstraint(
            model_name="user",
            constraint=models.CheckConstraint(
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
        ),
        migrations.AddConstraint(
            model_name="user",
            constraint=models.CheckConstraint(
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
        ),
        migrations.AddConstraint(
            model_name="user",
            constraint=models.CheckConstraint(
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
        ),
    ]
