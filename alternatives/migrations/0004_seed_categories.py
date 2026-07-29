from django.db import migrations


CATEGORIES = [
    {
        "code": "TRAVEL",
        "name": "여행",
        "display_order": 1,
    },
    {
        "code": "HEALTH",
        "name": "운동·건강",
        "display_order": 2,
    },
    {
        "code": "CULTURE",
        "name": "문화·여가",
        "display_order": 3,
    },
    {
        "code": "LIVING",
        "name": "생활·편의",
        "display_order": 4,
    },
    {
        "code": "DIGITAL",
        "name": "디지털·전자기기",
        "display_order": 5,
    },
    {
        "code": "FINANCE",
        "name": "재정",
        "display_order": 6,
    },
]


def seed_categories(apps, schema_editor):
    Category = apps.get_model("alternatives", "Category")

    for category in CATEGORIES:
        Category.objects.update_or_create(
            code=category["code"],
            defaults={
                "name": category["name"],
                "display_order": category["display_order"],
                "is_active": True,
            },
        )


def remove_categories(apps, schema_editor):
    Category = apps.get_model("alternatives", "Category")
    category_codes = [category["code"] for category in CATEGORIES]
    Category.objects.filter(code__in=category_codes).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("alternatives", "0003_alternative_valid_alternative_result"),
    ]

    operations = [
        migrations.RunPython(
            seed_categories,
            remove_categories,
        ),
    ]
