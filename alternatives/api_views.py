from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .services import AlternativeServiceError, generate_alternatives


def serialize_alternative(alternative):
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
    return {
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


class AlternativeGenerateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            consideration, alternatives = generate_alternatives(
                pk, request.user
            )
        except AlternativeServiceError as exc:
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

        categories = []
        for category in sorted(
            {alternative.category for alternative in alternatives},
            key=lambda value: (value.display_order, value.id),
        ):
            categories.append(
                {
                    "id": category.id,
                    "code": category.code,
                    "name": category.name,
                    "emoji": category.emoji,
                    "alternatives": [
                        serialize_alternative(alternative)
                        for alternative in sorted(
                            alternatives, key=lambda value: value.slot
                        )
                        if alternative.category_id == category.id
                    ],
                }
            )
        return Response(
            {
                "consideration_id": consideration.id,
                "status": consideration.status,
                "product": {
                    "name": consideration.product_name,
                    "price": consideration.product_price,
                },
                "categories": categories,
                "generated_at": timezone.localtime().isoformat(),
            },
            status=201,
        )
