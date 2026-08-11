"""AI 구매 의사결정·소비 기록 서비스 레이어 (docs/API.md §8.1, §8.5~§8.8).

`Consideration`을 `select_for_update()`로 잠근 뒤 상태·중복을 검사합니다.
Gemini 응답까지 수 초가 걸리므로 잠그지 않으면 두 번째 요청이 "아직
Decision이 없다"고 판단해 통과하고, `OneToOneField`의 UNIQUE 제약에 걸려
409가 아니라 500이 납니다. (§2.11) 소비 기록도 `OneToOneField`라 팝업
더블클릭에서 같은 일이 벌어집니다.
"""

import json

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from accounts.models import MONTHLY_BUDGET_RANGES
from alternatives.models import Alternative, LLMRequestLog
from products.models import Consideration

from .ai_service import (
    GeminiDecisionAdvisor,
    GeminiRequestError,
    GeminiTimeoutError,
)
from .models import DECISION_KEY_POINT_COUNT, Decision, SpendingRecord


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
):
    """구매 기록 수정 (§8.7).

    바꿀 수 있는 값은 구매 상태와 만족도뿐입니다. 상품 정보와 스냅샷은
    기록 당시 값이므로 건드리지 않습니다.
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
