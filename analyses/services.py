"""AI 구매 의사결정 서비스 레이어 (docs/API.md §8.1).

`Consideration`을 `select_for_update()`로 잠근 뒤 상태·중복을 검사합니다.
Gemini 응답까지 수 초가 걸리므로 잠그지 않으면 두 번째 요청이 "아직
Decision이 없다"고 판단해 통과하고, `OneToOneField`의 UNIQUE 제약에 걸려
409가 아니라 500이 납니다. (§2.11)
"""

import json

from django.conf import settings
from django.db import transaction

from alternatives.models import Alternative, LLMRequestLog
from products.models import Consideration

from .ai_service import (
    GeminiDecisionAdvisor,
    GeminiRequestError,
    GeminiTimeoutError,
)
from .models import DECISION_KEY_POINT_COUNT, Decision


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
