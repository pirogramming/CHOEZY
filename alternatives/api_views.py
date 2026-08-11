from django.utils import timezone
from products.models import Consideration
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import MONTHLY_BUDGET_RANGES
from core.responses import service_error_response

from .models import Alternative
from .services import (
    AlternativeServiceError,
    generate_alternatives,
    regenerate_alternative,
)
from .visualization import format_price


COMPARISON_COLUMNS = {
    Consideration.CompareCriterion.PRICE: {
        "key": "price",
        "label": "가격",
    },
    Consideration.CompareCriterion.DURATION: {
        "key": "duration",
        "label": "지속 가능 기간",
    },
    Consideration.CompareCriterion.EXPECTED_EFFECT: {
        "key": "expected_effect",
        "label": "기대 효과",
    },
    Consideration.CompareCriterion.AVAILABLE_BUDGET: {
        "key": "available_budget",
        "label": "가용 예산",
    },
}

# 소비 기록의 당시 예산 스냅샷(docs/API.md §8.4)도 같은 구간을 쓰므로
# 정의는 accounts에 두고 여기서는 가져다 씁니다.
BUDGET_RANGES = MONTHLY_BUDGET_RANGES


# 금액 표기는 기회비용 시각화 페이지와 같은 규칙을 써야 합니다.
format_budget_amount = format_price


def compare_with_budget(price, budget_code, budget_display):
    minimum, maximum = BUDGET_RANGES[budget_code]
    base = {
        "budget_code": budget_code,
        "budget_display": budget_display,
        "budget_min": minimum,
        "budget_max": maximum,
        "difference_min": None,
        "difference_max": None,
    }
    if price is None:
        return {
            **base,
            "status": "NOT_APPLICABLE",
            "display": "해당 없음",
        }
    if price < minimum:
        difference_min = minimum - price
        difference_max = maximum - price if maximum is not None else None
        if difference_max is None:
            display = f"월 예산 대비 최소 {format_budget_amount(difference_min)} 여유"
        else:
            display = (
                "월 예산 대비 "
                f"{format_budget_amount(difference_min)}~"
                f"{format_budget_amount(difference_max)} 여유"
            )
        return {
            **base,
            "status": "UNDER",
            "difference_min": difference_min,
            "difference_max": difference_max,
            "display": display,
        }
    if maximum is not None and price > maximum:
        difference_min = price - maximum
        difference_max = price - minimum if minimum else None
        if difference_max is None:
            display = f"월 예산 대비 최소 {format_budget_amount(difference_min)} 초과"
        else:
            display = (
                "월 예산 대비 "
                f"{format_budget_amount(difference_min)}~"
                f"{format_budget_amount(difference_max)} 초과"
            )
        return {
            **base,
            "status": "OVER",
            "difference_min": difference_min,
            "difference_max": difference_max,
            "display": display,
        }
    if maximum is None:
        return {
            **base,
            "status": "UNKNOWN",
            "display": "정확한 월 예산 확인 필요",
        }
    return {
        **base,
        "status": "WITHIN",
        "display": "월 예산 범위 내",
    }


def serialize_alternative(alternative, history=None):
    item = alternative.item
    is_quantity = alternative.result_type == "QUANTITY"
    if is_quantity:
        chart = {
            "type": "COUNT",
            "value": float(alternative.equivalent_quantity),
            "unit_label": item.unit_label,
            "caption": alternative.display_text,
        }
    else:
        chart = {
            "type": "GROWTH",
            "principal": alternative.unit_price,
            "future_value": alternative.future_value,
            "gain_amount": alternative.future_value - alternative.unit_price,
            "caption": alternative.display_text,
        }
    result = {
        "id": alternative.id,
        "slot": alternative.slot,
        "version": alternative.version,
        "is_current": alternative.is_current,
        "unit_price": alternative.unit_price,
        "unit_price_display": (
            f"{alternative.unit_price:,}원" if is_quantity else None
        ),
        "duration": alternative.duration,
        "duration_display": alternative.duration or "—",
        "expected_effect": alternative.expected_effect,
        "ai_reason": alternative.ai_reason,
        "result_type": alternative.result_type,
        "equivalent_quantity": (
            str(alternative.equivalent_quantity) if is_quantity else None
        ),
        "future_value": alternative.future_value,
        "display_text": alternative.display_text,
        "chart": chart,
        "item": {
            "id": item.id,
            "name": item.name,
            "unit_label": item.unit_label,
            "spec_note": item.spec_note,
            "calc_type": item.calc_type,
            "source_name": item.source_name,
            "source_url": item.source_url,
            "effective_date": str(item.effective_date),
        },
    }
    if history is not None:
        result["history"] = history
    return result


def serialize_consideration(consideration, alternatives, include_history=False):
    alternatives = list(alternatives)
    history_map = {}
    if include_history and alternatives:
        histories = Alternative.objects.filter(
            consideration=consideration,
            is_current=False,
        ).order_by("-version")
        for historical in histories:
            history_map.setdefault(
                (historical.category_id, historical.slot), []
            ).append(
                {
                    "id": historical.id,
                    "version": historical.version,
                    "display_text": historical.display_text,
                    "created_at": timezone.localtime(
                        historical.created_at
                    ).isoformat(),
                }
            )

    categories = []
    category_ids = []
    for alternative in alternatives:
        if alternative.category_id not in category_ids:
            category_ids.append(alternative.category_id)
            categories.append(alternative.category)
    category_results = []
    for category in categories:
        category_results.append(
            {
                "id": category.id,
                "code": category.code,
                "name": category.name,
                "emoji": category.emoji,
                "alternatives": [
                    serialize_alternative(
                        alternative,
                        history_map.get(
                            (alternative.category_id, alternative.slot), []
                        )
                        if include_history
                        else None,
                    )
                    for alternative in alternatives
                    if alternative.category_id == category.id
                ],
            }
        )
    generated_at = (
        timezone.localtime(max(item.created_at for item in alternatives)).isoformat()
        if alternatives
        else None
    )
    return {
        "consideration_id": consideration.id,
        "status": consideration.status,
        "product": {
            "name": consideration.product_name,
            "price": consideration.product_price,
            "duration_display": consideration.product_duration or "—",
            "expected_effect": consideration.product_expected_effect or "—",
        },
        "categories": category_results,
        "generated_at": generated_at,
    }


class AlternativeGenerateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            consideration, alternatives = generate_alternatives(
                pk, request.user
            )
        except AlternativeServiceError as exc:
            return service_error_response(exc)

        alternatives.sort(
            key=lambda item: (
                item.category.display_order,
                item.category_id,
                item.slot,
            )
        )
        return Response(
            serialize_consideration(consideration, alternatives), status=201
        )


class AlternativeListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            consideration = Consideration.objects.get(pk=pk, user=request.user)
        except Consideration.DoesNotExist:
            return service_error_response(
                AlternativeServiceError(
                    "NOT_FOUND", "구매 고민을 찾을 수 없습니다.", 404
                )
            )

        alternatives = Alternative.objects.filter(
            consideration=consideration,
            is_current=True,
        ).select_related("category", "item").order_by(
            "category__display_order", "category_id", "slot"
        )
        category_code = request.query_params.get("category")
        if category_code:
            alternatives = alternatives.filter(category__code=category_code)
        include_history = (
            request.query_params.get("include_history", "false").lower()
            == "true"
        )
        return Response(
            serialize_consideration(
                consideration, alternatives, include_history=include_history
            )
        )


class AlternativeRegenerateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            previous, alternative = regenerate_alternative(pk, request.user)
        except AlternativeServiceError as exc:
            return service_error_response(exc)

        result = serialize_alternative(alternative)
        result["category"] = {
            "id": alternative.category.id,
            "code": alternative.category.code,
            "name": alternative.category.name,
            "emoji": alternative.category.emoji,
        }
        result["previous_alternative_id"] = previous.id
        return Response(result, status=201)


def serialize_comparison_row(alternative, consideration):
    item = alternative.item
    is_quantity = alternative.result_type == "QUANTITY"
    if is_quantity:
        price = alternative.unit_price
        price_display = f"{price:,}원"
        chart = {
            "type": "COUNT",
            "value": float(alternative.equivalent_quantity),
            "unit_label": item.unit_label,
            "caption": (
                f"{consideration.product_name} = {alternative.display_text}"
            ),
        }
    else:
        price = None
        price_display = "—"
        chart = {
            "type": "GROWTH",
            "principal": alternative.unit_price,
            "future_value": alternative.future_value,
            "gain_amount": alternative.future_value - alternative.unit_price,
            "caption": alternative.display_text,
        }

    source_note = (
        f"{item.effective_date:%Y.%m} 기준 · {item.source_name}"
    )
    if not is_quantity:
        source_note += " · 세전"
    return {
        "alternative_id": alternative.id,
        "slot": alternative.slot,
        "name": item.name,
        "price": price,
        "price_display": price_display,
        "duration_display": alternative.duration or "—",
        "expected_effect": alternative.expected_effect,
        "available_budget": compare_with_budget(
            price,
            consideration.user.monthly_budget,
            consideration.user.get_monthly_budget_display(),
        ),
        "opportunity_cost": {
            "result_type": alternative.result_type,
            "equivalent_quantity": (
                str(alternative.equivalent_quantity)
                if is_quantity
                else None
            ),
            "future_value": alternative.future_value,
            "display_text": alternative.display_text,
        },
        "chart": chart,
        "source": {
            "name": item.source_name,
            "url": item.source_url,
            "effective_date": str(item.effective_date),
            "note": source_note,
        },
    }


class AlternativeComparisonAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            consideration = Consideration.objects.select_related("user").get(
                pk=pk, user=request.user
            )
        except Consideration.DoesNotExist:
            return service_error_response(
                AlternativeServiceError(
                    "NOT_FOUND", "구매 고민을 찾을 수 없습니다.", 404
                )
            )
        if consideration.status == Consideration.Status.DRAFT:
            return service_error_response(
                AlternativeServiceError(
                    "INVALID_STATUS",
                    "대안 생성 후 비교표를 조회할 수 있습니다.",
                    409,
                )
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
            return service_error_response(
                AlternativeServiceError(
                    "INVALID_STATUS",
                    "현재 비교할 대안이 없습니다.",
                    409,
                )
            )

        columns = [
            COMPARISON_COLUMNS[criterion]
            for criterion in COMPARISON_COLUMNS
            if criterion in consideration.compare_criteria
        ]
        tabs = []
        category_ids = []
        for alternative in alternatives:
            if alternative.category_id not in category_ids:
                category_ids.append(alternative.category_id)
                category = alternative.category
                tabs.append(
                    {
                        "category": {
                            "id": category.id,
                            "code": category.code,
                            "name": category.name,
                            "emoji": category.emoji,
                        },
                        "rows": [
                            serialize_comparison_row(item, consideration)
                            for item in alternatives
                            if item.category_id == category.id
                        ],
                    }
                )

        return Response(
            {
                "consideration_id": consideration.id,
                "product": {
                    "name": consideration.product_name,
                    "price": consideration.product_price,
                    "features": consideration.product_features,
                    "duration_display": (
                        consideration.product_duration or "—"
                    ),
                    "expected_effect": (
                        consideration.product_expected_effect or "—"
                    ),
                },
                "user_budget": {
                    "code": consideration.user.monthly_budget,
                    "display": consideration.user.get_monthly_budget_display(),
                },
                "columns": columns,
                "tabs": tabs,
            }
        )
