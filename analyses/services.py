"""AI 구매 의사결정·소비 기록 서비스 레이어 (docs/API.md §8.1, §8.5~§8.8).

`Consideration`을 `select_for_update()`로 잠근 뒤 상태·중복을 검사합니다.
Gemini 응답까지 수 초가 걸리므로 잠그지 않으면 두 번째 요청이 "아직
Decision이 없다"고 판단해 통과하고, `OneToOneField`의 UNIQUE 제약에 걸려
409가 아니라 500이 납니다. (§2.11) 소비 기록도 `OneToOneField`라 팝업
더블클릭에서 같은 일이 벌어집니다.
"""

import calendar
import json

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Avg, Count, Q, Sum
from django.utils import timezone

from accounts.models import MONTHLY_BUDGET_RANGES
from alternatives.models import Alternative, Category, LLMRequestLog
from products.models import Consideration

from .ai_service import (
    GeminiDecisionAdvisor,
    GeminiPatternAnalyst,
    GeminiRequestError,
    GeminiTimeoutError,
)
from .models import (
    DECISION_KEY_POINT_COUNT,
    Decision,
    SpendingPatternReport,
    SpendingRecord,
)


KEY_POINT_MAX_LENGTH = (
    Decision._meta.get_field("key_points").base_field.max_length
)


class DecisionServiceError(Exception):
    def __init__(self, code, message, status_code, details=None):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


def _build_prompt(consideration, alternatives):
    user = consideration.user
    payload = {
        "product": {
            "name": consideration.product_name,
            "price": consideration.product_price,
            "features": consideration.product_features,
            "purpose": consideration.get_purpose_display(),
            "purpose_detail": consideration.purpose_detail,
        },
        "consumer_profile": {
            "spending_types": [
                dict(user.SpendingType.choices).get(value, value)
                for value in user.spending_type
            ],
            "value_criteria": [
                dict(user.ValueCriterion.choices).get(value, value)
                for value in user.value_criteria
            ],
            "monthly_budget": user.get_monthly_budget_display(),
        },
        "alternatives": [
            {
                "category": alternative.category.name,
                "name": alternative.item.name,
                "opportunity_cost": alternative.display_text,
                "duration": alternative.duration,
                "expected_effect": alternative.expected_effect,
            }
            for alternative in alternatives
        ],
    }
    return (
        "당신은 사용자의 소비 결정을 돕는 분석가입니다. 아래 상품과 "
        "소비 프로필, 이미 계산된 기회비용을 근거로 구매 목적 적합도"
        "(purpose_fit), 예상 만족도(expected_satisfaction), 추천 의견"
        "(recommendation)을 각각 HIGH, MIDDLE, LOW 중 하나로 평가하세요. "
        f"key_points에는 판단 근거를 {DECISION_KEY_POINT_COUNT}개의 짧은 "
        "한국어 문장(각 40자 이내)으로 쓰고, summary에는 두세 문장의 "
        "종합 설명을 쓰세요. 점수나 확률, 새로운 가격을 만들지 말고 "
        "제공된 숫자만 인용하세요.\n"
        + json.dumps(payload, ensure_ascii=False)
    )


def _validate_response(response):
    if not isinstance(response, dict):
        raise GeminiRequestError("Gemini 응답 형식이 올바르지 않습니다.")

    validated = {}
    for field in ("purpose_fit", "expected_satisfaction", "recommendation"):
        value = response.get(field)
        if value not in Decision.Level.values:
            raise GeminiRequestError(
                f"{field}는 HIGH, MIDDLE, LOW 중 하나여야 합니다."
            )
        validated[field] = value

    summary = response.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        raise GeminiRequestError("summary가 필요합니다.")
    validated["summary"] = summary.strip()

    points = response.get("key_points")
    if not isinstance(points, list) or len(points) != DECISION_KEY_POINT_COUNT:
        raise GeminiRequestError(
            f"key_points는 {DECISION_KEY_POINT_COUNT}개여야 합니다."
        )
    key_points = []
    for point in points:
        if not isinstance(point, str) or not point.strip():
            raise GeminiRequestError("key_points 항목이 비어 있습니다.")
        key_points.append(point.strip()[:KEY_POINT_MAX_LENGTH])
    validated["key_points"] = key_points
    return validated


def _log(consideration, prompt, response, status):
    LLMRequestLog.objects.create(
        consideration=consideration,
        purpose=LLMRequestLog.Purpose.DECISION,
        model=settings.GEMINI_MODEL,
        prompt=prompt,
        response=response,
        status=status,
    )


def create_decision(consideration_id, user, advisor=None):
    advisor = advisor or GeminiDecisionAdvisor()
    prompt = ""
    response = None
    consideration = None
    try:
        with transaction.atomic():
            try:
                consideration = (
                    Consideration.objects.select_for_update(of=("self",))
                    .select_related("user")
                    .get(pk=consideration_id, user=user)
                )
            except Consideration.DoesNotExist as exc:
                raise DecisionServiceError(
                    "NOT_FOUND", "구매 고민을 찾을 수 없습니다.", 404
                ) from exc

            if consideration.status != Consideration.Status.GENERATED:
                raise DecisionServiceError(
                    "INVALID_STATUS",
                    "대안 생성이 끝난 고민만 의사결정을 만들 수 있습니다.",
                    409,
                    {
                        "status": [
                            f"현재 상태: {consideration.status}, "
                            f"필요한 상태: {Consideration.Status.GENERATED}"
                        ]
                    },
                )
            if Decision.objects.filter(consideration=consideration).exists():
                raise DecisionServiceError(
                    "ALREADY_EXISTS",
                    "이미 AI 의사결정이 생성된 고민입니다.",
                    409,
                )

            alternatives = list(
                Alternative.objects.filter(
                    consideration=consideration,
                    is_current=True,
                )
                .select_related("category", "item")
                .order_by("category__display_order", "category_id", "slot")
            )
            if not alternatives:
                raise DecisionServiceError(
                    "INVALID_STATUS",
                    "판단 근거로 쓸 대안이 없습니다.",
                    409,
                )

            prompt = _build_prompt(consideration, alternatives)
            response = advisor.advise(prompt)
            decision = Decision.objects.create(
                consideration=consideration,
                ai_model=settings.GEMINI_MODEL,
                **_validate_response(response),
            )
    except DecisionServiceError:
        raise
    except GeminiTimeoutError as exc:
        if consideration and prompt:
            _log(
                consideration,
                prompt,
                {"error": str(exc)},
                LLMRequestLog.Status.FAILED,
            )
        raise DecisionServiceError(
            "AI_TIMEOUT", "AI 응답 시간이 초과되었습니다.", 504
        ) from exc
    except GeminiRequestError as exc:
        if consideration and prompt:
            _log(
                consideration,
                prompt,
                {"error": str(exc)},
                LLMRequestLog.Status.FAILED,
            )
        raise DecisionServiceError(
            "AI_REQUEST_FAILED", "AI 의사결정 생성에 실패했습니다.", 502
        ) from exc

    _log(consideration, prompt, response, LLMRequestLog.Status.SUCCESS)
    return decision


# --------------------------------------------------------------------------
# 소비 기록 (docs/API.md §8.4~§8.8)
# --------------------------------------------------------------------------


# `Consideration.exclude_category`가 비어 있을 때 쓰는 값입니다. 구매 결정
# 팝업은 사용자 여정의 마지막 단계라 여기서 409를 주면 기록 자체를 잃습니다.
FALLBACK_CATEGORY = "기타"

# 소비 기록을 만들 수 있는 고민 상태입니다. `DECIDED`도 허용하는 이유는
# 최종 선택 폼(§8.3)이 먼저 상태를 바꿔놓을 수 있기 때문입니다. 중복 생성은
# 상태가 아니라 `ALREADY_EXISTS`가 막습니다.
SPENDING_RECORD_ALLOWED_STATUSES = frozenset(
    {
        Consideration.Status.GENERATED,
        Consideration.Status.DECIDED,
    }
)


class SpendingRecordServiceError(Exception):
    def __init__(self, code, message, status_code, details=None):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


def _budget_amount(user):
    """당시 예산 금액 스냅샷 (§8.4).

    구간의 하한을 씁니다. "200만원 이상"이면 2,000,000원입니다. 다만
    "10만원 이하"는 하한이 0이라 `spending_budget_snapshot_gt_0` 제약에
    걸리므로 상한을 대신 씁니다.
    """
    minimum, maximum = MONTHLY_BUDGET_RANGES[user.monthly_budget]
    return minimum or maximum


def _apply_purchase_status(record, purchase_status, satisfaction):
    """구매 상태에 맞춰 구매일·만족도를 정리합니다. (§8.5, §8.7)

    생성과 수정이 같은 규칙을 써야 합니다. `PURCHASED`에서 `DEFERRED`로
    바꿀 때 이전 값이 남아 있으면 `spending_status_fields_consistent`
    제약에 걸려 400이 아니라 500이 납니다.

    구매 확정 팝업에는 날짜 입력란이 없으므로 구매일은 서버가 채웁니다.
    """
    record.purchase_status = purchase_status

    if purchase_status == SpendingRecord.PurchaseStatus.PURCHASED:
        record.satisfaction = satisfaction
        if record.purchased_on is None:
            record.purchased_on = timezone.localdate()
    else:
        record.purchased_on = None
        record.satisfaction = None


def _save_validated(record):
    """`full_clean()`을 거쳐 저장합니다.

    `SpendingRecord.save()`는 `capture_snapshots()`만 부르고 검증은 하지
    않습니다. 건너뛰면 DB `CheckConstraint`가 `IntegrityError`를 던져
    400이 아니라 500이 됩니다. (§8.5)
    """
    try:
        record.full_clean()
    except ValidationError as exc:
        raise SpendingRecordServiceError(
            "VALIDATION_ERROR",
            "소비 기록을 저장할 수 없습니다.",
            400,
            exc.message_dict,
        ) from exc

    record.save()
    return record


def create_spending_record(
    consideration_id,
    user,
    purchase_status,
    satisfaction=None,
):
    """구매 결정 팝업의 소비 기록 생성 (§8.5).

    `Consideration`을 `select_for_update()`로 잠근 뒤 중복을 검사합니다.
    `SpendingRecord.consideration`은 `OneToOneField`라, 팝업 더블클릭으로
    두 요청이 겹치면 UNIQUE 제약에 걸려 409가 아니라 500이 납니다. (§2.11)
    """
    with transaction.atomic():
        try:
            consideration = (
                Consideration.objects.select_for_update(of=("self",))
                .select_related("user", "exclude_category", "final_choice")
                .get(pk=consideration_id, user=user)
            )
        except Consideration.DoesNotExist as exc:
            raise SpendingRecordServiceError(
                "NOT_FOUND", "구매 고민을 찾을 수 없습니다.", 404
            ) from exc

        if consideration.status not in SPENDING_RECORD_ALLOWED_STATUSES:
            raise SpendingRecordServiceError(
                "INVALID_STATUS",
                "대안 생성이 끝난 고민만 소비 기록을 남길 수 있습니다.",
                409,
                {
                    "status": [
                        f"현재 상태: {consideration.status}, "
                        f"필요한 상태: {Consideration.Status.GENERATED}"
                    ]
                },
            )

        if SpendingRecord.objects.filter(
            consideration=consideration
        ).exists():
            raise SpendingRecordServiceError(
                "ALREADY_EXISTS", "이미 소비 기록이 있는 고민입니다.", 409
            )

        record = SpendingRecord(
            user=user,
            consideration=consideration,
            # 요청에서 받지 않고 고민에서 따라갑니다. 다른 고민의 최종
            # 선택을 넣는 경로를 아예 만들지 않습니다. (§8.4)
            final_choice=getattr(consideration, "final_choice", None),
            category=(
                consideration.exclude_category.name
                if consideration.exclude_category_id
                else FALLBACK_CATEGORY
            ),
            product_name=consideration.product_name,
            product_price=consideration.product_price,
            product_url=consideration.product_url,
            image_url=consideration.image_url,
            budget_amount_snapshot=_budget_amount(user),
        )
        _apply_purchase_status(record, purchase_status, satisfaction)
        _save_validated(record)

        if consideration.status != Consideration.Status.DECIDED:
            consideration.status = Consideration.Status.DECIDED
            consideration.save(update_fields=["status", "updated_at"])

    return record


def update_spending_record(
    consideration_id,
    user,
    purchase_status,
    satisfaction=None,
    purpose=None,
):
    """구매 기록 수정 (§8.7).

    바꿀 수 있는 값은 구매 상태와 만족도, 목적입니다. 상품 정보와 나머지
    스냅샷은 기록 당시 값이므로 건드리지 않습니다.

    `purpose`가 `None`이면 목적을 그대로 둡니다. 요청에 목적이 없다고 해서
    지우면 안 됩니다.
    """
    with transaction.atomic():
        try:
            record = (
                SpendingRecord.objects.select_for_update(of=("self",))
                .select_related("user", "consideration")
                .get(consideration_id=consideration_id, user=user)
            )
        except SpendingRecord.DoesNotExist as exc:
            raise SpendingRecordServiceError(
                "NOT_FOUND", "소비 기록을 찾을 수 없습니다.", 404
            ) from exc

        _apply_purchase_status(record, purchase_status, satisfaction)

        if purpose is not None:
            record.purpose_snapshot = purpose

        _save_validated(record)

    return record


def get_spending_record(consideration_id, user):
    """소비 기록 상세 (§8.6).

    `decision`을 응답에 중첩하므로 미리 `select_related()`로 가져옵니다.
    """
    try:
        return SpendingRecord.objects.select_related(
            "consideration",
            "consideration__decision",
        ).get(consideration_id=consideration_id, user=user)
    except SpendingRecord.DoesNotExist as exc:
        raise SpendingRecordServiceError(
            "NOT_FOUND", "소비 기록을 찾을 수 없습니다.", 404
        ) from exc


def filter_spending_records(user, filters):
    """소비로그 목록 queryset (§8.8).

    정렬은 `SpendingRecord.Meta.ordering`(최신순)을 그대로 씁니다.
    """
    queryset = SpendingRecord.objects.filter(user=user)

    statuses = filters.get("purchase_status")
    if statuses:
        queryset = queryset.filter(purchase_status__in=statuses)

    category = filters.get("category")
    if category:
        queryset = queryset.filter(category=category)

    purpose = filters.get("purpose")
    if purpose:
        queryset = queryset.filter(purpose_snapshot=purpose)

    date_from = filters.get("date_from")
    if date_from:
        queryset = queryset.filter(recorded_on__gte=date_from)

    date_to = filters.get("date_to")
    if date_to:
        queryset = queryset.filter(recorded_on__lte=date_to)

    return queryset


# --------------------------------------------------------------------------
# 소비 기록 통계 (docs/API.md §8.9)
# --------------------------------------------------------------------------


# "다시 생각해볼 소비" 기준 점수입니다.
LOW_SATISFACTION_THRESHOLD = 3

# 리포트 도넛 차트에 이름을 그대로 노출하는 조각 수입니다. 나머지는
# "기타" 한 조각으로 묶습니다.
DONUT_TOP_SLICE_COUNT = 3

OTHERS_SLICE_NAME = "기타"


def _month_bounds(month_start):
    """`date(2026, 8, 1)` → 그 달의 1일과 말일."""
    last_day = calendar.monthrange(month_start.year, month_start.month)[1]
    return month_start, month_start.replace(day=last_day)


def _period(month_start):
    if month_start is None:
        return {
            "month": None,
            "label": "전체 기간",
            "date_from": None,
            "date_to": None,
        }

    date_from, date_to = _month_bounds(month_start)
    return {
        "month": month_start.strftime("%Y-%m"),
        "label": f"{month_start.year}년 {month_start.month}월",
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
    }


def _category_codes():
    """카테고리 이름 → 코드.

    `SpendingRecord.category`는 이름 문자열 스냅샷이라 코드가 없습니다.
    프론트가 분야별 색을 코드로 고정할 수 있도록 6행짜리 마스터에서
    찾아 붙입니다. 이름이 바뀐 뒤의 옛 기록은 `None`입니다.
    """
    return dict(Category.objects.values_list("name", "code"))


def _percentages(amounts):
    """금액 목록 → 정수 백분율 목록.

    반올림 때문에 합이 100에서 어긋나면 **가장 큰 조각이 차이를 흡수**해
    도넛에 빈틈이나 겹침이 생기지 않게 합니다. (§8.9)
    """
    total = sum(amounts)
    if not total:
        return [0] * len(amounts)

    ratios = [round(amount * 100 / total) for amount in amounts]
    gap = 100 - sum(ratios)
    if gap:
        largest = max(range(len(ratios)), key=lambda index: amounts[index])
        ratios[largest] += gap
    return ratios


def _by_category(purchased):
    rows = list(
        purchased.values("category")
        .annotate(amount=Sum("product_price"), count=Count("id"))
        .order_by("-amount", "category")
    )
    codes = _category_codes() if rows else {}
    ratios = _percentages([row["amount"] for row in rows])

    return [
        {
            "name": row["category"],
            "code": codes.get(row["category"]),
            "amount": row["amount"],
            "count": row["count"],
            "ratio": ratio,
        }
        for row, ratio in zip(rows, ratios)
    ]


def _donut_slices(by_category):
    """상위 3개 + 나머지를 묶은 "기타" 한 조각. (§8.9)"""
    if len(by_category) <= DONUT_TOP_SLICE_COUNT:
        return [
            {
                "name": row["name"],
                "code": row["code"],
                "ratio": row["ratio"],
                "is_others": False,
            }
            for row in by_category
        ]

    top = by_category[:DONUT_TOP_SLICE_COUNT]
    rest = by_category[DONUT_TOP_SLICE_COUNT:]
    slices = [
        {
            "name": row["name"],
            "code": row["code"],
            "ratio": row["ratio"],
            "is_others": False,
        }
        for row in top
    ]
    slices.append(
        {
            "name": OTHERS_SLICE_NAME,
            "code": None,
            # 상위 조각을 뺀 나머지로 계산해 합을 정확히 100으로 맞춥니다.
            "ratio": 100 - sum(row["ratio"] for row in top),
            "is_others": True,
            "items": [
                {
                    "name": row["name"],
                    "code": row["code"],
                    "ratio": row["ratio"],
                }
                for row in rest
            ],
        }
    )
    return slices


def _by_purpose(rated):
    rows = list(
        rated.values("purpose_snapshot")
        .annotate(
            count=Count("id"),
            average_satisfaction=Avg("satisfaction"),
        )
        .order_by("-average_satisfaction", "purpose_snapshot")
    )

    return [
        {
            "purpose": row["purpose_snapshot"],
            "count": row["count"],
            "average_satisfaction": round(row["average_satisfaction"], 1),
        }
        for row in rows
    ]


def build_spending_stats(user, month_start=None):
    """소비 기록 통계 (§8.9).

    소비로그 상단 카드와 초이지 리포트가 같은 응답을 씁니다. `month_start`가
    없으면 전체 기간입니다.

    표시 문자열이 아닌 **숫자만** 담아 돌려줍니다. 소비 패턴 분석(4일차)이
    이 값을 그대로 프롬프트 근거로 쓰기 때문입니다.
    """
    records = SpendingRecord.objects.filter(user=user)
    if month_start is not None:
        date_from, date_to = _month_bounds(month_start)
        records = records.filter(recorded_on__range=(date_from, date_to))

    purchased = records.filter(
        purchase_status=SpendingRecord.PurchaseStatus.PURCHASED
    )
    rated = records.filter(satisfaction__isnull=False)

    totals = records.aggregate(total_count=Count("id"))
    purchased_totals = purchased.aggregate(
        purchased_count=Count("id"),
        total_spent=Sum("product_price"),
        # 목적이 분명한 소비 — 구매 목적을 "기타"로 두거나 비워 둔 기록만
        # 제외합니다. 목적 항목이 늘어도 이 규칙은 그대로입니다. (§8.9)
        purposeful_count=Count(
            "id",
            filter=~Q(
                purpose_snapshot__in=["", Consideration.Purpose.ETC]
            ),
        ),
    )
    satisfaction_totals = rated.aggregate(average=Avg("satisfaction"))
    low = records.filter(
        satisfaction__lte=LOW_SATISFACTION_THRESHOLD
    ).aggregate(count=Count("id"), amount=Sum("product_price"))

    total_count = totals["total_count"]
    purchased_count = purchased_totals["purchased_count"]
    purposeful_count = purchased_totals["purposeful_count"]
    average = satisfaction_totals["average"]

    by_category = _by_category(purchased)
    by_purpose = _by_purpose(rated)

    return {
        "period": _period(month_start),
        "total_count": total_count,
        "purchased_count": purchased_count,
        "total_spent": purchased_totals["total_spent"] or 0,
        # 기록이 0건이면 0으로 나누게 되므로 분모를 먼저 확인합니다.
        "purchase_rate": (
            round(purchased_count * 100 / total_count) if total_count else 0
        ),
        "average_satisfaction": round(average, 1) if average else None,
        "purposeful_count": purposeful_count,
        # 분모는 구매 확정 건수입니다. 사지 않은 기록은 "소비"가 아닙니다.
        "purposeful_rate": (
            round(purposeful_count * 100 / purchased_count)
            if purchased_count
            else 0
        ),
        "by_category": by_category,
        "top_category": by_category[0] if by_category else None,
        "donut_slices": _donut_slices(by_category),
        "by_purpose": by_purpose,
        # `_by_purpose()`가 만족도 내림차순이라 양 끝이 최고·최저입니다.
        "highest_satisfaction_purpose": by_purpose[0] if by_purpose else None,
        "lowest_satisfaction_purpose": by_purpose[-1] if by_purpose else None,
        "low_satisfaction": {
            "threshold": LOW_SATISFACTION_THRESHOLD,
            "count": low["count"],
            "amount": low["amount"] or 0,
        },
    }


# --------------------------------------------------------------------------
# 소비 패턴 분석 (docs/API.md §8.10)
# --------------------------------------------------------------------------


# 분석 문장을 만들 만한 최소 기록 수입니다. 한두 건으로 "소비 습관"을
# 말하면 근거 없는 단정이 됩니다.
PATTERN_MIN_RECORD_COUNT = 3

SUMMARY_MAX_LENGTH = 200


class SpendingPatternServiceError(Exception):
    def __init__(self, code, message, status_code, details=None):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


def _pattern_evidence(stats):
    """프롬프트에 넣을 근거. 이미 계산된 숫자만 골라 담습니다."""
    top_category = stats["top_category"]
    highest = stats["highest_satisfaction_purpose"]
    lowest = stats["lowest_satisfaction_purpose"]

    def purpose_label(row):
        if not row or not row["purpose"]:
            return None
        return Consideration.Purpose(row["purpose"]).label

    return {
        "총_소비_기록_수": stats["total_count"],
        "구매_확정_건수": stats["purchased_count"],
        "구매_확정률_퍼센트": stats["purchase_rate"],
        "평균_만족도": stats["average_satisfaction"],
        "목적형_소비_비율_퍼센트": stats["purposeful_rate"],
        "가장_많이_소비한_분야": (
            top_category["name"] if top_category else None
        ),
        "가장_많이_소비한_분야_비율_퍼센트": (
            top_category["ratio"] if top_category else None
        ),
        "분야별_소비_비율": {
            row["name"]: row["ratio"] for row in stats["by_category"]
        },
        "만족도가_높은_구매_목적": purpose_label(highest),
        "만족도가_높은_구매_목적_점수": (
            highest["average_satisfaction"] if highest else None
        ),
        "만족도가_낮은_구매_목적": purpose_label(lowest),
        "만족도가_낮은_구매_목적_점수": (
            lowest["average_satisfaction"] if lowest else None
        ),
        "만족도_3점_이하_건수": stats["low_satisfaction"]["count"],
    }


def _build_pattern_prompt(user, evidence):
    profile = {
        "소비_성향": [
            dict(user.SpendingType.choices).get(value, value)
            for value in user.spending_type
        ],
        "중요_가치_기준": [
            dict(user.ValueCriterion.choices).get(value, value)
            for value in user.value_criteria
        ],
        "월_소비_예산": user.get_monthly_budget_display(),
    }
    return (
        "당신은 사용자의 소비 습관을 분석하는 상담가입니다. 아래 이미 "
        "계산된 소비 통계와 소비 프로필을 근거로, 이 사람의 소비 습관을 "
        "설명하는 한국어 문장을 두 문장 이내로 쓰세요.\n"
        "규칙:\n"
        "- 제공된 숫자만 인용하고 새로운 수치를 만들지 마세요.\n"
        "- 비율이나 점수를 문장에 직접 쓰지 말고 경향을 설명하세요.\n"
        "- 사용자를 탓하지 말고 관찰한 경향을 담백하게 쓰세요.\n"
        f"- 전체 {SUMMARY_MAX_LENGTH}자를 넘기지 마세요.\n"
        "예시: \"목적이 분명한 소비일수록 만족도가 높고, 신중하게 비교한 "
        "후 구매하는 경향이 있어요\"\n"
        + json.dumps(
            {"소비_통계": evidence, "소비_프로필": profile},
            ensure_ascii=False,
        )
    )


def _validate_pattern_response(response):
    if not isinstance(response, dict):
        raise GeminiRequestError("Gemini 응답 형식이 올바르지 않습니다.")

    summary = response.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        raise GeminiRequestError("summary가 필요합니다.")
    return summary.strip()[:SUMMARY_MAX_LENGTH]


def create_spending_pattern_report(user, analyst=None):
    """소비 패턴 분석 생성 (§8.10).

    §8.9 통계를 근거로 넣고 AI에게는 문장만 받습니다. 비율·만족도는 이미
    계산되어 있으므로 AI가 숫자를 새로 만들 이유가 없습니다.
    """
    analyst = analyst or GeminiPatternAnalyst()
    stats = build_spending_stats(user)

    if stats["total_count"] < PATTERN_MIN_RECORD_COUNT:
        raise SpendingPatternServiceError(
            "NOT_ENOUGH_RECORDS",
            "소비 기록이 충분하지 않아 분석할 수 없습니다.",
            409,
            {
                "record_count": [
                    f"현재 {stats['total_count']}건, "
                    f"최소 {PATTERN_MIN_RECORD_COUNT}건 필요"
                ]
            },
        )

    evidence = _pattern_evidence(stats)
    prompt = _build_pattern_prompt(user, evidence)

    try:
        response = analyst.analyze(prompt)
        summary = _validate_pattern_response(response)
    except GeminiTimeoutError as exc:
        raise SpendingPatternServiceError(
            "AI_TIMEOUT", "AI 응답 시간이 초과되었습니다.", 504
        ) from exc
    except GeminiRequestError as exc:
        raise SpendingPatternServiceError(
            "AI_REQUEST_FAILED", "소비 패턴 분석에 실패했습니다.", 502
        ) from exc

    return SpendingPatternReport.objects.create(
        user=user,
        summary=summary,
        record_count=stats["total_count"],
        stats_snapshot=evidence,
        ai_model=settings.GEMINI_MODEL,
    )


def get_latest_spending_pattern_report(user):
    """가장 최근 분석 (§8.10). `Meta.ordering`이 최신순입니다."""
    report = SpendingPatternReport.objects.filter(user=user).first()
    if report is None:
        raise SpendingPatternServiceError(
            "NOT_FOUND", "소비 패턴 분석을 찾을 수 없습니다.", 404
        )
    return report


def count_spending_records(user):
    """분석 신선도 판단용 현재 기록 수 (§8.10)."""
    return SpendingRecord.objects.filter(user=user).count()
