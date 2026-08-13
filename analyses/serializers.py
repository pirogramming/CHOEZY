"""AI 의사결정·소비 기록 직렬화 (docs/API.md §8.1, §8.6, §8.8).

화면에 그대로 출력할 문자열과 그래프 수치는 서버가 완성해서 내려보냅니다.
프론트가 `HIGH`/`MIDDLE`/`LOW`를 보고 라벨·막대 높이·색을 분기하지 않도록
`chart`에 담습니다. (§2.10)
"""

from datetime import datetime

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers

from products.models import Consideration

from .models import Decision, SpendingRecord


# 게이지 바늘 각도와 막대 높이에 쓰는 등급별 수치 (0~100)
LEVEL_SCORES = {
    Decision.Level.HIGH: 88,
    Decision.Level.MIDDLE: 55,
    Decision.Level.LOW: 32,
}

LEVEL_COLORS = {
    Decision.Level.HIGH: "#2ECC71",
    Decision.Level.MIDDLE: "#F4C430",
    Decision.Level.LOW: "#F5811F",
}

BAR_LABELS = [
    ("purpose_fit", "구매 목적 적합도"),
    ("expected_satisfaction", "예상 만족도"),
    ("recommendation", "추천도"),
]


def _bar(key, label, level):
    return {
        "key": key,
        "label": label,
        "level": level,
        "level_display": Decision.Level(level).label,
        "score": LEVEL_SCORES[level],
        "color": LEVEL_COLORS[level],
    }


def serialize_decision(decision):
    bars = [
        _bar(key, label, getattr(decision, key))
        for key, label in BAR_LABELS
    ]
    # 반원 게이지: 0도가 왼쪽 끝(낮음), 180도가 오른쪽 끝(높음)
    gauge = {**bars[0], "angle_deg": round(bars[0]["score"] * 1.8, 1)}
    return {
        "id": decision.id,
        "consideration_id": decision.consideration_id,
        "purpose_fit": decision.purpose_fit,
        "purpose_fit_display": decision.get_purpose_fit_display(),
        "expected_satisfaction": decision.expected_satisfaction,
        "expected_satisfaction_display": (
            decision.get_expected_satisfaction_display()
        ),
        "recommendation": decision.recommendation,
        "recommendation_display": decision.get_recommendation_display(),
        "key_points": list(decision.key_points),
        "summary": decision.summary,
        "ai_model": decision.ai_model,
        "created_at": timezone.localtime(decision.created_at).isoformat(),
        "chart": {"gauge": gauge, "bars": bars},
    }


# 값이 없는 자리에 화면이 그대로 출력할 문자열입니다. (§2.10)
EMPTY_DISPLAY = "—"

# 소비 기록 화면의 상태 배지 문구입니다. 모델 label("구매 확정")과 다른 이유는
# 화면 문구가 더 짧기 때문입니다. 모델 label은 admin에서 그대로 쓰므로
# 바꾸지 않고, 화면용 문자열만 여기서 만듭니다. (§2.10)
PURCHASE_STATUS_DISPLAY = {
    SpendingRecord.PurchaseStatus.PURCHASED: "구매함",
    SpendingRecord.PurchaseStatus.DEFERRED: "구매 보류",
    SpendingRecord.PurchaseStatus.NOT_PURCHASED: "구매 안 함",
}


def format_won(amount):
    """소비 기록 금액 표기 — `"2,200,000원"`.

    `alternatives.visualization.format_price`는 만원 단위로 딱 떨어지면
    `"220만원"`으로 줄이지만, 소비로그와 기록 상세는 원 단위를 그대로
    보여주므로 재사용하지 않습니다.
    """
    return f"{amount:,}원"


def _date_display(value):
    return value.strftime("%Y.%m.%d") if value else EMPTY_DISPLAY


def _purpose_display(record):
    if not record.purpose_snapshot:
        return EMPTY_DISPLAY
    return Consideration.Purpose(record.purpose_snapshot).label


def _criteria_display(record):
    return [
        Consideration.CompareCriterion(code).label
        for code in record.compare_criteria_snapshot
    ]


def _budget_display(record):
    """예산 구간 라벨.

    `monthly_budget_snapshot`은 choices 없는 `CharField`라
    `get_..._display()`를 쓸 수 없으므로 `User.MonthlyBudget`에서 찾습니다.
    """
    code = record.monthly_budget_snapshot
    if not code:
        return EMPTY_DISPLAY
    return dict(get_user_model().MonthlyBudget.choices).get(code, code)


def serialize_spending_record(record):
    """소비 기록 상세 (§8.6).

    `decision`은 §8.1 응답을 그대로 중첩합니다. 게이지 각도·막대 높이·색
    매핑이 의사결정 화면과 어긋나지 않도록 `serialize_decision()`을
    재사용합니다.

    호출 전에 `consideration`과 `consideration__decision`을
    `select_related()`로 가져와야 추가 쿼리가 나가지 않습니다.
    """
    # 역참조 OneToOne이 비어 있으면 Django가 AttributeError를 상속한 예외를
    # 던지므로 getattr 기본값으로 잡힙니다.
    decision = getattr(record.consideration, "decision", None)
    budget_amount = record.budget_amount_snapshot

    return {
        "id": record.id,
        "consideration_id": record.consideration_id,
        "final_choice_id": record.final_choice_id,
        "purchase_status": record.purchase_status,
        "purchase_status_display": PURCHASE_STATUS_DISPLAY[
            record.purchase_status
        ],
        "recorded_on": record.recorded_on.isoformat(),
        "recorded_on_display": _date_display(record.recorded_on),
        "purchased_on": (
            record.purchased_on.isoformat() if record.purchased_on else None
        ),
        "satisfaction": record.satisfaction,
        "satisfaction_display": (
            f"{record.satisfaction}점"
            if record.satisfaction is not None
            else EMPTY_DISPLAY
        ),
        "category": record.category,
        "product_name": record.product_name,
        "product_price": record.product_price,
        "product_price_display": format_won(record.product_price),
        "product_url": record.product_url,
        "image_url": record.image_url,
        # 응답 키에서 `_snapshot`을 뗍니다. 스냅샷 여부는 저장 구조의
        # 관심사이고 화면에는 "그 기록의 목적·기준·예산"일 뿐입니다. (§8.6)
        "purpose": record.purpose_snapshot,
        "purpose_display": _purpose_display(record),
        "purpose_detail": record.purpose_detail_snapshot,
        "compare_criteria": list(record.compare_criteria_snapshot),
        "compare_criteria_display": _criteria_display(record),
        "monthly_budget": record.monthly_budget_snapshot,
        "monthly_budget_display": _budget_display(record),
        "budget_amount": budget_amount,
        "budget_amount_display": (
            format_won(budget_amount)
            if budget_amount is not None
            else EMPTY_DISPLAY
        ),
        "created_at": timezone.localtime(record.created_at).isoformat(),
        "decision": serialize_decision(decision) if decision else None,
    }


def serialize_spending_record_item(record):
    """소비로그 목록 카드 (§8.8).

    카드에 그리는 필드만 담습니다. 스냅샷 전체와 `decision`은 상세에서만
    내려갑니다 — 목록 30건마다 게이지 데이터를 만들 이유가 없습니다.
    """
    return {
        "id": record.id,
        "consideration_id": record.consideration_id,
        "purchase_status": record.purchase_status,
        "purchase_status_display": PURCHASE_STATUS_DISPLAY[
            record.purchase_status
        ],
        "recorded_on": record.recorded_on.isoformat(),
        "recorded_on_display": _date_display(record.recorded_on),
        "satisfaction": record.satisfaction,
        "satisfaction_display": (
            f"{record.satisfaction}점"
            if record.satisfaction is not None
            else EMPTY_DISPLAY
        ),
        "category": record.category,
        "purpose_display": _purpose_display(record),
        "product_name": record.product_name,
        "product_price": record.product_price,
        "product_price_display": format_won(record.product_price),
        "image_url": record.image_url,
    }


class SpendingRecordWriteSerializer(serializers.Serializer):
    """소비 기록 생성·수정 입력 (§8.5, §8.7).

    구매 결정 팝업이 보내는 값은 탭 선택과 별점 둘뿐입니다. 구매일과 상품
    정보, 스냅샷은 서버가 채웁니다. (§8.4)
    """

    purchase_status = serializers.ChoiceField(
        choices=SpendingRecord.PurchaseStatus.choices,
    )

    satisfaction = serializers.IntegerField(
        min_value=1,
        max_value=5,
        required=False,
        allow_null=True,
    )

    def validate(self, attrs):
        purchase_status = attrs["purchase_status"]
        satisfaction = attrs.get("satisfaction")

        if purchase_status == SpendingRecord.PurchaseStatus.PURCHASED:
            if satisfaction is None:
                raise serializers.ValidationError(
                    {"satisfaction": "구매 확정 시 만족도가 필요합니다."}
                )
        elif satisfaction is not None:
            raise serializers.ValidationError(
                {
                    "satisfaction": (
                        "구매 보류 또는 구매 안 함에는 만족도를 저장할 수 "
                        "없습니다."
                    )
                }
            )

        return attrs


class SpendingRecordFilterSerializer(serializers.Serializer):
    """소비로그 목록 필터 (§8.8)."""

    purchase_status = serializers.CharField(required=False)

    category = serializers.CharField(required=False)

    purpose = serializers.ChoiceField(
        choices=Consideration.Purpose.choices,
        required=False,
    )

    date_from = serializers.DateField(required=False)

    date_to = serializers.DateField(required=False)

    page = serializers.IntegerField(min_value=1, required=False, default=1)

    page_size = serializers.IntegerField(
        min_value=1,
        max_value=50,
        required=False,
        default=10,
    )

    def validate_purchase_status(self, value):
        """콤마 구분 다중 값 (§8.8).

        탭 하나가 상태 하나에 대응하지 않습니다. 구매 보류도 목록에 함께
        노출하므로 프론트가 탭마다 필요한 상태를 조합해 보냅니다.
        """
        statuses = [item.strip() for item in value.split(",") if item.strip()]
        invalid = [
            item
            for item in statuses
            if item not in SpendingRecord.PurchaseStatus.values
        ]
        if invalid:
            raise serializers.ValidationError(
                f"허용되지 않는 값입니다: {', '.join(invalid)}"
            )
        return statuses

    def validate(self, attrs):
        date_from = attrs.get("date_from")
        date_to = attrs.get("date_to")
        if date_from and date_to and date_from > date_to:
            raise serializers.ValidationError(
                {"date_to": "종료일이 시작일보다 빠릅니다."}
            )
        return attrs


def _satisfaction_display(score):
    return f"{score}점" if score is not None else EMPTY_DISPLAY


def _ratio_display(ratio):
    return f"{ratio}%"


def _category_stat(row):
    return {
        "name": row["name"],
        "code": row["code"],
        "amount": row["amount"],
        "amount_display": format_won(row["amount"]),
        "count": row["count"],
        "ratio": row["ratio"],
        "ratio_display": _ratio_display(row["ratio"]),
    }


def _purpose_stat(row):
    purpose = row["purpose"]
    return {
        "purpose": purpose,
        "purpose_display": (
            Consideration.Purpose(purpose).label if purpose else EMPTY_DISPLAY
        ),
        "count": row["count"],
        "average_satisfaction": row["average_satisfaction"],
        "average_satisfaction_display": _satisfaction_display(
            row["average_satisfaction"]
        ),
    }


def _donut_slice(row):
    payload = {
        "name": row["name"],
        "code": row["code"],
        "ratio": row["ratio"],
        "ratio_display": _ratio_display(row["ratio"]),
        "is_others": row["is_others"],
    }
    if row["is_others"]:
        payload["items"] = [
            {
                "name": item["name"],
                "code": item["code"],
                "ratio": item["ratio"],
                "ratio_display": _ratio_display(item["ratio"]),
            }
            for item in row["items"]
        ]
    return payload


def serialize_spending_stats(stats):
    """소비 기록 통계 (§8.9).

    `build_spending_stats()`가 만든 숫자에 화면용 문자열을 입힙니다.
    집계와 표기를 나눠 두는 이유는 소비 패턴 분석(4일차)이 숫자 쪽만
    프롬프트에 쓰기 때문입니다.
    """
    average = stats["average_satisfaction"]
    top_category = stats["top_category"]
    highest = stats["highest_satisfaction_purpose"]
    lowest = stats["lowest_satisfaction_purpose"]
    low = stats["low_satisfaction"]

    return {
        "period": stats["period"],
        "total_count": stats["total_count"],
        "purchased_count": stats["purchased_count"],
        "total_spent": stats["total_spent"],
        "total_spent_display": format_won(stats["total_spent"]),
        "purchase_rate": stats["purchase_rate"],
        "purchase_rate_display": _ratio_display(stats["purchase_rate"]),
        "average_satisfaction": average,
        "average_satisfaction_display": _satisfaction_display(average),
        "top_category": (
            _category_stat(top_category) if top_category else None
        ),
        "by_category": [
            _category_stat(row) for row in stats["by_category"]
        ],
        "chart": {
            "slices": [
                _donut_slice(row) for row in stats["donut_slices"]
            ],
        },
        "by_purpose": [_purpose_stat(row) for row in stats["by_purpose"]],
        "highest_satisfaction_purpose": (
            _purpose_stat(highest) if highest else None
        ),
        "lowest_satisfaction_purpose": (
            _purpose_stat(lowest) if lowest else None
        ),
        "low_satisfaction": {
            "threshold": low["threshold"],
            "count": low["count"],
            "amount": low["amount"],
            "amount_display": format_won(low["amount"]),
        },
    }


class SpendingStatsFilterSerializer(serializers.Serializer):
    """소비 기록 통계 파라미터 (§8.9)."""

    month = serializers.CharField(required=False)

    def validate_month(self, value):
        """`"2026-08"` → 그 달 1일. 형식이 틀리면 400입니다."""
        try:
            return datetime.strptime(value, "%Y-%m").date()
        except ValueError:
            raise serializers.ValidationError(
                "YYYY-MM 형식이어야 합니다."
            ) from None
