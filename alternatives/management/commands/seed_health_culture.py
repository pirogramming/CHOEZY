from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from alternatives.models import AlternativeItem, Category


EFFECTIVE_DATE = date(2026, 8, 6)

SEED_ITEMS = {
    Category.Code.HEALTH: [
        {
            "name": "헬스장 1개월",
            "unit_label": "개월",
            "average_price": 45000,
            "spec_note": "서울시 공공체육시설 월 회원 성인 기준",
            "source_name": "서울특별시 체육시설관리사업소",
            "source_url": "https://stadium.seoul.go.kr/lecture/info-2-2",
        },
        {
            "name": "따릉이 정기권 1개월",
            "unit_label": "개월",
            "average_price": 5000,
            "spec_note": "서울시 공공자전거 30일 정기권, 1회 1시간권 기준",
            "source_name": "서울자전거 따릉이",
            "source_url": "https://www.bikeseoul.com/info/infoCoupon.do",
        },
        {
            "name": "수영장 1개월",
            "unit_label": "개월",
            "average_price": 60000,
            "spec_note": "서울시 공공수영장 성인 강습 주 3회, 1개월 기준",
            "source_name": "서울특별시 체육시설관리사업소",
            "source_url": "https://stadium.seoul.go.kr/lecture/fee",
        },
        {
            "name": "골프 연습장 1개월",
            "unit_label": "개월",
            "average_price": 100000,
            "spec_note": "서울시 공공 실내골프장 월 회원 성인 기준, 레슨 제외",
            "source_name": "서울특별시 체육시설관리사업소",
            "source_url": "https://stadium.seoul.go.kr/lecture/info",
        },
        {
            "name": "종합건강검진 1회",
            "unit_label": "회",
            "average_price": 400000,
            "spec_note": "성인 기본 종합검진 1회, 비급여 기준",
            "source_name": "한국건강관리협회",
            "source_url": "https://www.kahp.or.kr/ho/hlthChk/cprsvchk/cprsvchkIntro.do",
        },
    ],
    Category.Code.CULTURE: [
        {
            "name": "영화 관람 1회",
            "unit_label": "회",
            "average_price": 15000,
            "spec_note": "성인 2D 일반관, 주말 기준 1인 1매",
            "source_name": "CGV",
            "source_url": "http://www.cgv.co.kr/theaters/theaterPrice.aspx",
        },
        {
            "name": "뮤지컬 관람 1회",
            "unit_label": "회",
            "average_price": 150000,
            "spec_note": "대극장 공연 R석 기준 1인 1매",
            "source_name": "NOL 티켓",
            "source_url": "https://nol.yanolja.com/ticket/products/L0000142",
        },
        {
            "name": "콘서트 관람 1회",
            "unit_label": "회",
            "average_price": 165000,
            "spec_note": "국내 아티스트 단독 공연 일반석 기준 1인 1매",
            "source_name": "NOL 티켓",
            "source_url": "https://nol.yanolja.com/ticket/products/26011092",
        },
        {
            "name": "전시회 관람 1회",
            "unit_label": "회",
            "average_price": 23000,
            "spec_note": "유료 기획전 성인 1인 기준",
            "source_name": "NOL 티켓",
            "source_url": "https://nol.yanolja.com/ticket/products/26006222",
        },
        {
            "name": "OTT 구독 1개월",
            "unit_label": "개월",
            "average_price": 13500,
            "spec_note": "넷플릭스 스탠다드 개인 요금제 월 결제 기준",
            "source_name": "netflix",
            "source_url": "https://www.netflix.com/kr/",
        },
        {
            "name": "음악 스트리밍 1개월",
            "unit_label": "개월",
            "average_price": 9790,
            "spec_note": "멜론 스트리밍 티켓 요금제 월 결제 기준",
            "source_name": "Melon",
            "source_url": "https://www.melon.com/buy/pamphlet/all.htm",
        },
        {
            "name": "놀이공원 종일권 1회",
            "unit_label": "회",
            "average_price": 62000,
            "spec_note": "에버랜드 종일권 대인 1매, 시즌 요금제 평균 기준",
            "source_name": "에버랜드 스마트예약",
            "source_url": "https://www.everland.com/everland/promotion/usage-fee",
        },
        {
            "name": "프로야구 관람 1회",
            "unit_label": "회",
            "average_price": 18000,
            "spec_note": "잠실야구장 내야 일반석 주말 경기 기준 1인 1매",
            "source_name": "LG 트윈스 좌석 가격 안내",
            "source_url": "https://www.lgtwins.com/ticket/general",
        },
        {
            "name": "도서 구입 1권",
            "unit_label": "권",
            "average_price": 18000,
            "spec_note": "국내 신간 단행본 평균 정가 기준",
            "source_name": "대한출판문화협회",
            "source_url": "https://www.kpa21.or.kr/kpa-data/statistics/",
        },
        {
            "name": "웹툰 결제 1개월",
            "unit_label": "개월",
            "average_price": 10000,
            "spec_note": "네이버웹툰 쿠키 100개 결제 기준, 월 1회",
            "source_name": "네이버웹툰",
            "source_url": "https://comic.naver.com",
        },
        {
            "name": "전자책 구독 1개월",
            "unit_label": "개월",
            "average_price": 11900,
            "spec_note": "밀리의 서재 월 구독 요금제 기준",
            "source_name": "밀리의 서재",
            "source_url": "https://www.millie.co.kr/v4/product/subscribe",
        },
    ],
}


class Command(BaseCommand):
    help = "운동·건강 및 문화·여가 AlternativeItem을 입력합니다."

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