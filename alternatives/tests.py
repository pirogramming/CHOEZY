from django.core.management import call_command
from django.test import TestCase

from .management.commands.seed_living_digital import EFFECTIVE_DATE
from .models import AlternativeItem, Category


class LivingDigitalSeedTests(TestCase):
    def test_seed_command_creates_twelve_items_idempotently(self):
        call_command("seed_living_digital", verbosity=0)

        seeded = AlternativeItem.objects.filter(
            category__code__in=[
                Category.Code.LIVING,
                Category.Code.DIGITAL,
            ],
            effective_date=EFFECTIVE_DATE,
        )
        self.assertEqual(seeded.count(), 12)
        self.assertTrue(
            all(
                item.calc_type == AlternativeItem.CalcType.UNIT_PRICE
                for item in seeded
            )
        )
        self.assertTrue(all(item.average_price > 0 for item in seeded))
        self.assertTrue(all(item.source_url for item in seeded))

        call_command("seed_living_digital", verbosity=0)

        self.assertEqual(seeded.count(), 12)

    def test_seed_command_updates_existing_item(self):
        call_command("seed_living_digital", verbosity=0)
        item = AlternativeItem.objects.get(
            category__code=Category.Code.LIVING,
            name="서울 지하철 기본요금 1회",
            effective_date=EFFECTIVE_DATE,
        )
        item.average_price = 1
        item.save(update_fields=["average_price"])

        call_command("seed_living_digital", verbosity=0)

        item.refresh_from_db()
        self.assertEqual(item.average_price, 1550)
