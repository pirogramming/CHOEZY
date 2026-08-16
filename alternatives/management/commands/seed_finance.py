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
        {
            "name": "CMA 계좌 (RP형, 연 3%)",
            "unit_label": "원",
            "average_price": 1000000,
            "spec_note": "신한투자증권 RP형 CMA, 세전 연 3.00% 수익률 기준",
            "calc_type": AlternativeItem.CalcType.DEPOSIT,
            "calc_params": {
                "period_month": 12,
                "return_rate": 3,
            },
            "source_name": "신한투자증권 CMA 안내",
            "source_url": "https://m.shinhansec.com/mweb/fnin/fcma/ffcma0001",
        },
        {
            "name": "파킹통장 (연 3%)",
            "unit_label": "원",
            "average_price": 1000000,
            "spec_note": "우대금리 조건 충족 시 연 3% 안팎 파킹통장 기준",
            "calc_type": AlternativeItem.CalcType.DEPOSIT,
            "calc_params": {
                "period_month": 12,
                "return_rate": 3,
            },
            "source_name": "2026 파킹통장 금리 비교",
            "source_url": "https://www.quami.co.kr/211",
        },
        {
            "name": "채권형 ETF 투자 (KODEX 국고채10년액티브)",
            "unit_label": "좌",
            "average_price": 104060,
            "spec_note": "국내 대표 국고채 10년 채권형 ETF(KODEX 국고채10년액티브, 삼성자산운용), 2026.08.12 기준 만기수익률(YTM) 연 4.22%",
            "calc_type": AlternativeItem.CalcType.INVESTMENT,
            "calc_params": {
                "period_month": 12,
                "return_rate": 4.22,
                "base_date": "2026-08-12",
            },
            "source_name": "FunETF (삼성자산운용)",
            "source_url": "https://www.funetf.co.kr/product/etf/view/KR7471230003",
        },
        {
            "name": "배당주 ETF 투자 (TIGER 배당성장)",
            "unit_label": "좌",
            "average_price": 36210,
            "spec_note": "코스피 배당성장 50 추종 배당주 ETF(TIGER 배당성장, 미래에셋자산운용), 2026.08.14 기준 최근 1년 수익률 약 50.3%",
            "calc_type": AlternativeItem.CalcType.INVESTMENT,
            "calc_params": {
                "period_month": 12,
                "return_rate": 50,
                "base_date": "2026-08-14",
            },
            "source_name": "Investing.com",
            "source_url": "https://www.investing.com/etfs/miraeasset-tiger-dividend-growth",
        },
        {
            "name": "금 투자 (KODEX 골드선물(H))",
            "unit_label": "좌",
            "average_price": 24335,
            "spec_note": "국내 대표 금 가격 연동 ETF(KODEX 골드선물(H), 삼성자산운용), 2026.08 기준 최근 1년 수익률 약 35%",
            "calc_type": AlternativeItem.CalcType.INVESTMENT,
            "calc_params": {
                "period_month": 12,
                "return_rate": 35,
                "base_date": "2026-08-14",
            },
            "source_name": "FunETF / Investing.com",
            "source_url": "https://www.funetf.co.kr/product/etf/view/KR7132030008",
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