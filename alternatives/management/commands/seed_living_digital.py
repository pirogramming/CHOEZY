from datetime import date

from django.core.management.base import BaseCommand
from django.db import transaction

from alternatives.models import AlternativeItem, Category


EFFECTIVE_DATE = date(2026, 8, 3)

SEED_ITEMS = {
    Category.Code.LIVING: [
        {
            "name": "서울 지하철 기본요금 1회",
            "unit_label": "회",
            "average_price": 1550,
            "spec_note": "성인 교통카드, 10km 이내 기본요금 기준",
            "source_name": "서울시 물가정보",
            "source_url": (
                "https://sftc.seoul.go.kr/seoul/mulga/main/"
                "contents.do?menuNo=200021"
            ),
        },
        {
            "name": "서울 시내버스 기본요금 1회",
            "unit_label": "회",
            "average_price": 1500,
            "spec_note": "성인 교통카드, 서울 간선·지선버스 기준",
            "source_name": "서울시 물가정보",
            "source_url": (
                "https://sftc.seoul.go.kr/seoul/mulga/main/"
                "contents.do?menuNo=200022"
            ),
        },
        {
            "name": "스타벅스 카페 아메리카노 Tall 1잔",
            "unit_label": "잔",
            "average_price": 4700,
            "spec_note": "스타벅스 카페 아메리카노 Tall 사이즈 기준",
            "source_name": "스타벅스 코리아",
            "source_url": (
                "https://www.starbucks.co.kr/menu/"
                "drink_view.do?product_cd=18"
            ),
        },
        {
            "name": "BBQ 황금올리브치킨 1마리",
            "unit_label": "마리",
            "average_price": 23000,
            "spec_note": "BBQ 황금올리브치킨 기본 한 마리 기준",
            "source_name": "BBQ치킨",
            "source_url": "https://m.bbq.co.kr/menu/menuList_ajax.asp",
        },
        {
            "name": "동대문엽기떡볶이 엽기메뉴 1개",
            "unit_label": "개",
            "average_price": 14000,
            "spec_note": "엽기메뉴 기본맛, 토핑·배달비 제외 기준",
            "source_name": "동대문엽기떡볶이",
            "source_url": "https://www.yupdduk.com/sub/menu/yup-menu",
        },
        {
            "name": "서울역–부산역 KTX 일반실 왕복",
            "unit_label": "왕복",
            "average_price": 119600,
            "spec_note": "성인 일반실 정상운임 59,800원 편도 2회 기준",
            "source_name": "한국철도공사",
            "source_url": (
                "https://info.korail.com/info/selectBbsNttView.do"
                "?bbsNo=199&key=911&nttNo=6263"
            ),
        },
    ],
    Category.Code.DIGITAL: [
        {
            "name": "Apple iPhone 17 256GB",
            "unit_label": "대",
            "average_price": 1290000,
            "spec_note": "Apple Store 자급제 기본 모델 256GB 기준",
            "source_name": "Apple 대한민국",
            "source_url": (
                "https://www.apple.com/kr/shop/buy-iphone/iphone-17"
            ),
        },
        {
            "name": "Apple iPad 128GB Wi-Fi",
            "unit_label": "대",
            "average_price": 749000,
            "spec_note": "Apple Store 기본형 iPad 128GB Wi-Fi 기준",
            "source_name": "Apple 대한민국",
            "source_url": "https://www.apple.com/kr/shop/buy-ipad/ipad",
        },
        {
            "name": "Apple MacBook Air 13 M5",
            "unit_label": "대",
            "average_price": 1790000,
            "spec_note": "13형 M5 기본 구성 시작 가격 기준",
            "source_name": "Apple 대한민국",
            "source_url": (
                "https://www.apple.com/kr/shop/buy-mac/"
                "macbook-air/13-%EB%AA%A8%EB%8D%B8"
            ),
        },
        {
            "name": "Apple AirPods 4",
            "unit_label": "개",
            "average_price": 199000,
            "spec_note": "액티브 노이즈 캔슬링 미탑재 기본 모델 기준",
            "source_name": "Apple 대한민국",
            "source_url": "https://www.apple.com/kr/airpods/",
        },
        {
            "name": "Apple Watch Series 11",
            "unit_label": "개",
            "average_price": 599000,
            "spec_note": "Apple Watch Series 11 기본 구성 시작 가격 기준",
            "source_name": "Apple 대한민국",
            "source_url": "https://www.apple.com/kr/shop/buy-watch",
        },
        {
            "name": "Microsoft 365 Personal 1개월",
            "unit_label": "개월",
            "average_price": 12500,
            "spec_note": "개인 1명 월간 결제 기준",
            "source_name": "Microsoft 대한민국",
            "source_url": (
                "https://www.microsoft.com/ko-kr/microsoft-365/"
                "buy/compare-all-microsoft-365-products"
            ),
        },
    ],
}


class Command(BaseCommand):
    help = "생활·편의 및 디지털·전자기기 AlternativeItem을 입력합니다."

    @transaction.atomic
    def handle(self, *args, **options):
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
