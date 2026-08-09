from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from alternatives.models import AlternativeItem, Category


EFFECTIVE_DATE = date(2026, 8, 6)

SEED_ITEMS = {
    Category.Code.TRAVEL: [
        {
            "name": "국내 당일치기 여행",
            "unit_label": "회",
            "average_price": 69000,
            "spec_note": "2025 국민여행조사 기준 국내 당일여행 1회 평균 지출액",
            "source_name": "한국문화관광연구원",
            "source_url": "https://know.tour.go.kr/",
        },
        {
            "name": "국내 1박 2일 여행",
            "unit_label": "회",
            "average_price": 221000,
            "spec_note": "2025 국민여행조사 기준 국내 숙박여행 1회 평균 지출액",
            "source_name": "한국문화관광연구원",
            "source_url": "https://know.tour.go.kr/",
        },
        {
            "name": "제주도 2박 3일 여행",
            "unit_label": "회",
            "average_price": 450000,
            "spec_note": "2026년 제주관광홍보사무소에서 공개한 제주 2박 3일 패키지 가격대(45~47만원)를 참고한 1인 기준 가격",
            "source_name": "제주관광홍보사무소",
            "source_url": "https://www.visitjeju.or.kr/",
        },
        {
            "name": "일본 3박 4일 여행",
            "unit_label": "회",
            "average_price": 817175,
            "spec_note": "2026년 하나투어에서 공개한 일본 3박 4일 상품 4종의 시작 가격 평균",
            "source_name": "하나투어",
            "source_url": "https://www.hanatour.com/",
        },
        {
            "name": "동남아 3박 4일 여행",
            "unit_label": "회",
            "average_price": 530800,
            "spec_note": "2026년 하나투어에서 공개한 다낭 4일 상품의 1인 기준 시작 가격",
            "source_name": "하나투어",
            "source_url": "https://www.hanatour.com/",
        },
    ],
}


class Command(BaseCommand):
    help = "여행 AlternativeItem을 입력합니다."

    @transaction.atomic
    def handle(self, *args, **options):
        unfilled = [
            item["name"]
            for items in SEED_ITEMS.values()
            for item in items
            if not item["average_price"] or not item["source_url"]
        ]

        if unfilled:
            raise CommandError(
                "가격 또는 출처가 비어 있는 항목이 있습니다: "
                + ", ".join(unfilled)
            )

        created_count = 0
        existing_count = 0

        for category_code, items in SEED_ITEMS.items():
            category = Category.objects.get(code=category_code)

            for item_data in items:
                defaults = {
                    key: value
                    for key, value in item_data.items()
                    if key != "name"
                }

                _, created = AlternativeItem.objects.update_or_create(
                    category=category,
                    name=item_data["name"],
                    effective_date=EFFECTIVE_DATE,
                    defaults={
                        **defaults,
                        "calc_type": AlternativeItem.CalcType.UNIT_PRICE,
                        "calc_params": {},
                        "is_active": True,
                    },
                )

                if created:
                    created_count += 1
                else:
                    existing_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"시드 완료: 생성 {created_count}개, 기존 {existing_count}개"
            )
        )