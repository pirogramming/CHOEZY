from django.utils import timezone
from products.models import Consideration
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Alternative
from .services import (
    AlternativeServiceError,
    generate_alternatives,
    regenerate_alternative,
)


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


def error_response(exc):
    return Response(
        {
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            }
        },
        status=exc.status_code,
    )


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
            return error_response(exc)

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
            return error_response(
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
            return error_response(exc)

        result = serialize_alternative(alternative)
        result["category"] = {
            "id": alternative.category.id,
            "code": alternative.category.code,
            "name": alternative.category.name,
            "emoji": alternative.category.emoji,
        }
        result["previous_alternative_id"] = previous.id
        return Response(result, status=201)
