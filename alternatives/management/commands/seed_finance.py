from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from alternatives.models import AlternativeItem, Category


EFFECTIVE_DATE = date(2026, 8, 6)

SEED_ITEMS = {
    Category.Code.FINANCE: [
        {
            "name": "정기적금 (연 3%)",
            "unit_label": "월",
            "average_price": 300000,
            "spec_note": "12개월 만기, 연 3% 금리 정기적금 기준",
            "calc_type": AlternativeItem.CalcType.SAVINGS,
            "calc_params": {
                "period_month": 12,
                "return_rate": 3,
            },
            "source_name": "금융감독원 금융상품통합비교공시",
            "source_url": "https://finlife.fss.or.kr/finlife/svings/fdrmEnty/list.do?menuNo=700003",
        },
        {
            "name": "정기적금 (연 6%)",
            "unit_label": "월",
            "average_price": 100000,
            "spec_note": "12개월 만기, 연 6% 금리 정기적금 기준",
            "calc_type": AlternativeItem.CalcType.SAVINGS,
            "calc_params": {
                "period_month": 12,
                "return_rate": 6,
            },
            "source_name": "금융감독원 금융상품통합비교공시",
            "source_url": "https://finlife.fss.or.kr/finlife/svings/fdrmEnty/list.do?menuNo=700003",
        },
        {
            "name": "예금 (연 3%)",
            "unit_label": "원",
            "average_price": 1000000,
            "spec_note": "12개월 만기, 연 3% 금리 정기예금 기준",
            "calc_type": AlternativeItem.CalcType.DEPOSIT,
            "calc_params": {
                "period_month": 12,
                "return_rate": 3,
            },
            "source_name": "금융감독원 금융상품통합비교공시",
            "source_url": "https://finlife.fss.or.kr/finlife/svings/fdrmDpst/list.do?menuNo=700002",
        },
        {
            "name": "예금 (연 6%)",
            "unit_label": "원",
            "average_price": 2000000,
            "spec_note": "12개월 만기, 연 6% 금리 정기예금 기준",
            "calc_type": AlternativeItem.CalcType.DEPOSIT,
            "calc_params": {
                "period_month": 12,
                "return_rate": 6,
            },
            "source_name": "금융감독원 금융상품통합비교공시",
            "source_url": "https://finlife.fss.or.kr/finlife/svings/fdrmDpst/list.do?menuNo=700002",
        },
        {
            "name": "KODEX 200 ETF 투자",
            "unit_label": "좌",
            "average_price": 98265,
            "spec_note": "국내 순자산 1위 ETF(KODEX 200, 삼성자산운용), 2026.08.10 기준 최근 1년 수익률 약 71%",
            "calc_type": AlternativeItem.CalcType.INVESTMENT,
            "calc_params": {
                "period_month": 12,
                "return_rate": 71,
                "base_date": "2026-08-10",
            },
            "source_name": "삼성자산운용 FunETF",
            "source_url": "https://www.funetf.co.kr/product/etf/view/KR7069500007",
        },
    ],
}


class Command(BaseCommand):
    help = "재정 AlternativeItem을 입력합니다."

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