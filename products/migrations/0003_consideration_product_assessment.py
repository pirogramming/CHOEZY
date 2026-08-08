from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0002_alter_consideration_purpose"),
    ]

    operations = [
        migrations.AddField(
            model_name="consideration",
            name="product_duration",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="consideration",
            name="product_expected_effect",
            field=models.TextField(blank=True),
        ),
    ]
