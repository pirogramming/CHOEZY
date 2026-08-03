import json

from django.conf import settings
from django.db import transaction

from analyses.calculator import calculate_opportunity_cost, is_calculable
from products.models import Consideration

from .ai_service import (
    GeminiAlternativeSelector,
    GeminiRequestError,
    GeminiTimeoutError,
)
from .models import Alternative, AlternativeItem, LLMRequestLog


class AlternativeServiceError(Exception):
    def __init__(self, code, message, status_code, details=None):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


def _build_prompt(consideration, candidates):
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
        "categories": [
            {
                "code": category.code,
                "name": category.name,
                "candidates": [
                    {
                        "item_id": item.id,
                        "name": item.name,
                        "calc_type": item.calc_type,
                        "spec_note": item.spec_note,
                    }
                    for item in items
                ],
            }
            for category, items in candidates
        ],
    }
    return (
        "당신은 사용자의 소비 결정을 돕는 추천 도우미입니다. "
        "각 카테고리에서 서로 다른 후보를 정확히 3개 선택하세요. "
        "item_id는 제공된 후보에서만 고르고, 슬롯은 1, 2, 3을 한 번씩 "
        "사용하세요. UNIT_PRICE 항목에는 duration, expected_effect, "
        "ai_reason을 한국어로 작성하세요. 그 외 항목은 item_id, slot, "
        "ai_reason만 작성하세요. 가격이나 출처를 만들지 마세요.\n"
        + json.dumps(payload, ensure_ascii=False)
    )


def _validate_response(response, candidates):
    if not isinstance(response, dict) or not isinstance(
        response.get("selections"), list
    ):
        raise GeminiRequestError("Gemini 응답 형식이 올바르지 않습니다.")

    candidate_map = {
        category.code: {item.id: item for item in items}
        for category, items in candidates
    }
    selections = response["selections"]
    if not all(isinstance(entry, dict) for entry in selections):
        raise GeminiRequestError("Gemini 응답 형식이 올바르지 않습니다.")
    if {entry.get("category_code") for entry in selections} != set(candidate_map):
        raise GeminiRequestError("Gemini가 요청하지 않은 카테고리를 반환했습니다.")

    validated = []
    for entry in selections:
        code = entry.get("category_code")
        items = entry.get("items")
        if (
            not isinstance(items, list)
            or len(items) != 3
            or not all(isinstance(item, dict) for item in items)
        ):
            raise GeminiRequestError("카테고리별 대안은 정확히 3개여야 합니다.")
        if {item.get("slot") for item in items} != {1, 2, 3}:
            raise GeminiRequestError("대안 슬롯은 1, 2, 3이어야 합니다.")
        item_ids = [item.get("item_id") for item in items]
        ids_are_integers = all(type(item_id) is int for item_id in item_ids)
        ids_are_unique = all(
            item_ids.count(item_id) == 1 for item_id in item_ids
        )
        ids_are_candidates = ids_are_integers and all(
            item_id in candidate_map[code] for item_id in item_ids
        )
        if not (ids_are_integers and ids_are_unique and ids_are_candidates):
            raise GeminiRequestError("유효하지 않은 대안 항목이 선택됐습니다.")

        for selection in items:
            item = candidate_map[code][selection["item_id"]]
            reason = selection.get("ai_reason")
            if not isinstance(reason, str) or not reason.strip():
                raise GeminiRequestError("ai_reason이 필요합니다.")
            if item.calc_type == AlternativeItem.CalcType.UNIT_PRICE:
                for field in ("duration", "expected_effect"):
                    value = selection.get(field)
                    if not isinstance(value, str) or not value.strip():
                        raise GeminiRequestError(f"{field}이 필요합니다.")
            validated.append((code, item, selection))
    return validated


def _log(consideration, purpose, prompt, response, status):
    LLMRequestLog.objects.create(
        consideration=consideration,
        purpose=purpose,
        model=settings.GEMINI_MODEL,
        prompt=prompt,
        response=response,
        status=status,
    )


def generate_alternatives(consideration_id, user, selector=None):
    selector = selector or GeminiAlternativeSelector()
    prompt = ""
    response = None
    consideration = None
    try:
        with transaction.atomic():
            try:
                consideration = (
                    Consideration.objects.select_for_update(of=("self",))
                    .select_related("user", "exclude_category")
                    .get(pk=consideration_id, user=user)
                )
            except Consideration.DoesNotExist as exc:
                raise AlternativeServiceError(
                    "NOT_FOUND", "구매 고민을 찾을 수 없습니다.", 404
                ) from exc

            if consideration.status != Consideration.Status.DRAFT:
                raise AlternativeServiceError(
                    "INVALID_STATUS", "이미 대안이 생성된 고민입니다.", 409
                )

            categories = list(
                consideration.categories.filter(is_active=True).order_by(
                    "display_order", "id"
                )
            )
            if consideration.exclude_category_id:
                categories = [
                    category
                    for category in categories
                    if category.id != consideration.exclude_category_id
                ]
            if not categories or len(categories) > settings.MAX_CATEGORY_SELECTION:
                raise AlternativeServiceError(
                    "INVALID_CATEGORIES",
                    "비교 카테고리는 1개 이상 3개 이하여야 합니다.",
                    409,
                )

            candidates = []
            shortages = []
            for category in categories:
                items = [
                    item
                    for item in category.alternative_items.filter(
                        is_active=True
                    ).order_by("id")
                    if is_calculable(item, consideration.product_price)
                ]
                if len(items) < 3:
                    shortages.append(
                        f"{category.code}: 계산 가능한 활성 항목 "
                        f"{len(items)}개 (최소 3개 필요)"
                    )
                candidates.append((category, items))
            if shortages:
                raise AlternativeServiceError(
                    "NO_CANDIDATE_ITEMS",
                    "사용할 수 있는 대안 데이터가 부족합니다.",
                    409,
                    {"category": shortages},
                )

            prompt = _build_prompt(consideration, candidates)
            response = selector.select(prompt)
            validated = _validate_response(response, candidates)

            created = []
            category_by_code = {
                category.code: category for category, _ in candidates
            }
            for code, item, selection in validated:
                calculation = calculate_opportunity_cost(
                    item, consideration.product_price
                )
                duration = calculation.duration or selection["duration"].strip()
                expected_effect = (
                    calculation.expected_effect
                    or selection["expected_effect"].strip()
                )
                created.append(
                    Alternative.objects.create(
                        consideration=consideration,
                        category=category_by_code[code],
                        item=item,
                        slot=selection["slot"],
                        version=1,
                        is_current=True,
                        unit_price=calculation.unit_price,
                        duration=duration,
                        expected_effect=expected_effect,
                        ai_reason=selection["ai_reason"].strip(),
                        result_type=calculation.result_type,
                        equivalent_quantity=calculation.equivalent_quantity,
                        future_value=calculation.future_value,
                        display_text=calculation.display_text,
                    )
                )
            consideration.status = Consideration.Status.GENERATED
            consideration.save(update_fields=["status", "updated_at"])
    except AlternativeServiceError:
        raise
    except GeminiTimeoutError as exc:
        if consideration and prompt:
            _log(
                consideration,
                LLMRequestLog.Purpose.GENERATE,
                prompt,
                {"error": str(exc)},
                LLMRequestLog.Status.FAILED,
            )
        raise AlternativeServiceError(
            "AI_TIMEOUT", "AI 응답 시간이 초과되었습니다.", 504
        ) from exc
    except GeminiRequestError as exc:
        if consideration and prompt:
            _log(
                consideration,
                LLMRequestLog.Purpose.GENERATE,
                prompt,
                {"error": str(exc)},
                LLMRequestLog.Status.FAILED,
            )
        raise AlternativeServiceError(
            "AI_REQUEST_FAILED", "AI 대안 생성에 실패했습니다.", 502
        ) from exc

    _log(
        consideration,
        LLMRequestLog.Purpose.GENERATE,
        prompt,
        response,
        LLMRequestLog.Status.SUCCESS,
    )
    return consideration, created


def _build_regenerate_prompt(consideration, alternative, candidates):
    payload = {
        "product": {
            "name": consideration.product_name,
            "price": consideration.product_price,
            "purpose": consideration.get_purpose_display(),
        },
        "consumer_profile": {
            "spending_types": consideration.user.spending_type,
            "value_criteria": consideration.user.value_criteria,
            "monthly_budget": consideration.user.get_monthly_budget_display(),
        },
        "category": {
            "code": alternative.category.code,
            "name": alternative.category.name,
        },
        "slot": alternative.slot,
        "previous_item": alternative.item.name,
        "candidates": [
            {
                "item_id": item.id,
                "name": item.name,
                "calc_type": item.calc_type,
                "spec_note": item.spec_note,
            }
            for item in candidates
        ],
    }
    return (
        "기존 추천과 겹치지 않는 새 대안 1개를 후보에서 선택하세요. "
        "응답은 selections 배열에 해당 카테고리 1개, items 배열에 항목 "
        "1개만 넣으세요. slot은 제공된 값을 사용하세요. UNIT_PRICE이면 "
        "duration, expected_effect, ai_reason을 한국어로 작성하고, 재정형이면 "
        "item_id, slot, ai_reason만 작성하세요. 가격과 출처는 만들지 마세요.\n"
        + json.dumps(payload, ensure_ascii=False)
    )


def _validate_regeneration_response(response, alternative, candidates):
    if not isinstance(response, dict):
        raise GeminiRequestError("Gemini 응답 형식이 올바르지 않습니다.")
    selections = response.get("selections")
    if not isinstance(selections, list) or len(selections) != 1:
        raise GeminiRequestError("재생성 대안은 정확히 1개여야 합니다.")
    category_selection = selections[0]
    if (
        not isinstance(category_selection, dict)
        or category_selection.get("category_code") != alternative.category.code
    ):
        raise GeminiRequestError("Gemini가 다른 카테고리를 반환했습니다.")
    items = category_selection.get("items")
    if (
        not isinstance(items, list)
        or len(items) != 1
        or not isinstance(items[0], dict)
    ):
        raise GeminiRequestError("재생성 대안은 정확히 1개여야 합니다.")

    selection = items[0]
    candidate_map = {item.id: item for item in candidates}
    item_id = selection.get("item_id")
    if type(item_id) is not int or item_id not in candidate_map:
        raise GeminiRequestError("유효하지 않은 대안 항목이 선택됐습니다.")
    if selection.get("slot") != alternative.slot:
        raise GeminiRequestError("Gemini가 잘못된 슬롯을 반환했습니다.")
    reason = selection.get("ai_reason")
    if not isinstance(reason, str) or not reason.strip():
        raise GeminiRequestError("ai_reason이 필요합니다.")

    item = candidate_map[item_id]
    if item.calc_type == AlternativeItem.CalcType.UNIT_PRICE:
        for field in ("duration", "expected_effect"):
            value = selection.get(field)
            if not isinstance(value, str) or not value.strip():
                raise GeminiRequestError(f"{field}이 필요합니다.")
    return item, selection


def regenerate_alternative(alternative_id, user, selector=None):
    selector = selector or GeminiAlternativeSelector()
    prompt = ""
    response = None
    consideration = None
    previous = None
    try:
        with transaction.atomic():
            try:
                target = Alternative.objects.select_related(
                    "consideration", "category", "item"
                ).get(pk=alternative_id, consideration__user=user)
            except Alternative.DoesNotExist as exc:
                raise AlternativeServiceError(
                    "NOT_FOUND", "대안을 찾을 수 없습니다.", 404
                ) from exc

            consideration = (
                Consideration.objects.select_for_update(of=("self",))
                .select_related("user")
                .get(pk=target.consideration_id)
            )
            previous = Alternative.objects.select_related(
                "category", "item"
            ).get(pk=target.pk)
            if not previous.is_current:
                raise AlternativeServiceError(
                    "INVALID_STATUS", "현재 대안만 재생성할 수 있습니다.", 409
                )
            if consideration.status != Consideration.Status.GENERATED:
                raise AlternativeServiceError(
                    "INVALID_STATUS", "대안을 재생성할 수 없는 상태입니다.", 409
                )

            current_item_ids = Alternative.objects.filter(
                consideration=consideration,
                is_current=True,
            ).values_list("item_id", flat=True)
            candidates = [
                item
                for item in AlternativeItem.objects.filter(
                    category=previous.category,
                    is_active=True,
                ).exclude(id__in=current_item_ids).order_by("id")
                if is_calculable(item, consideration.product_price)
            ]
            if not candidates:
                raise AlternativeServiceError(
                    "NO_CANDIDATE_ITEMS",
                    "재생성에 사용할 대안 데이터가 부족합니다.",
                    409,
                    {"category": [previous.category.code]},
                )

            prompt = _build_regenerate_prompt(
                consideration, previous, candidates
            )
            response = selector.select(prompt)
            item, selection = _validate_regeneration_response(
                response, previous, candidates
            )
            calculation = calculate_opportunity_cost(
                item, consideration.product_price
            )
            duration = calculation.duration or selection["duration"].strip()
            expected_effect = (
                calculation.expected_effect
                or selection["expected_effect"].strip()
            )

            previous.is_current = False
            previous.save(update_fields=["is_current", "updated_at"])
            created = Alternative.objects.create(
                consideration=consideration,
                category=previous.category,
                item=item,
                slot=previous.slot,
                version=previous.version + 1,
                is_current=True,
                unit_price=calculation.unit_price,
                duration=duration,
                expected_effect=expected_effect,
                ai_reason=selection["ai_reason"].strip(),
                result_type=calculation.result_type,
                equivalent_quantity=calculation.equivalent_quantity,
                future_value=calculation.future_value,
                display_text=calculation.display_text,
            )
    except AlternativeServiceError:
        raise
    except GeminiTimeoutError as exc:
        if consideration and prompt:
            _log(
                consideration,
                LLMRequestLog.Purpose.REGENERATE,
                prompt,
                {"error": str(exc)},
                LLMRequestLog.Status.FAILED,
            )
        raise AlternativeServiceError(
            "AI_TIMEOUT", "AI 응답 시간이 초과되었습니다.", 504
        ) from exc
    except GeminiRequestError as exc:
        if consideration and prompt:
            _log(
                consideration,
                LLMRequestLog.Purpose.REGENERATE,
                prompt,
                {"error": str(exc)},
                LLMRequestLog.Status.FAILED,
            )
        raise AlternativeServiceError(
            "AI_REQUEST_FAILED", "AI 대안 재생성에 실패했습니다.", 502
        ) from exc

    _log(
        consideration,
        LLMRequestLog.Purpose.REGENERATE,
        prompt,
        response,
        LLMRequestLog.Status.SUCCESS,
    )
    return previous, created
