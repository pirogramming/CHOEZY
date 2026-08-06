"""기회비용 시각화 페이지가 쓰는 표시용 데이터 (docs/API.md §7).

막대그래프는 "상품 가격 = 이 대안 N개"를 그립니다. 그래서 막대가 되는 것은
수량 환산(`result_type = QUANTITY`) 대안뿐입니다. 재정형(`FUTURE_VALUE`)은
나눗셈이 아니라 "그 돈을 대신 굴리면 얼마"라서 개수가 없고(§7.5), 막대에
끼워 넣으면 항상 1블록짜리 막대가 되어 숫자가 오히려 왜곡됩니다. 그래서
`financial_costs`로 갈라서 문장으로 내려줍니다.

숫자는 모두 `Alternative`에 저장된 계산 결과를 그대로 씁니다. 여기서 다시
계산하지 않습니다 — 화면마다 다른 숫자가 나오면 안 됩니다.
"""

from decimal import ROUND_DOWN, Decimal

from .models import Alternative


# `static/css/opportunity_cost.css`에 정의된 막대 색 클래스입니다.
# (막대 배경 클래스, 개수 텍스트 클래스) 순서이고, 막대 개수만큼 순환합니다.
BAR_PALETTE = (
    ("pink", "pink-text"),
    ("yellow", "yellow-text"),
    ("orange", "orange-text"),
    ("travel", "pink-text"),
)


def format_price(amount):
    """만원 단위로 딱 떨어지면 "220만원", 아니면 "1,234,500원"."""
    if amount % 10_000 == 0:
        return f"{amount // 10_000}만원"

    return f"{amount:,}원"


def format_quantity(quantity):
    """수량 표기 규칙 (docs/API.md §7.4).

    1 이상이면 정수로 내림, 1 미만이면 소수 첫째 자리까지 내림입니다.
    반올림하지 않는 이유는 §7.4와 같습니다 — 기회비용을 실제보다 크게
    보여주면 안 됩니다.
    """
    if quantity >= 1:
        return str(int(quantity))

    return str(quantity.quantize(Decimal("0.1"), rounding=ROUND_DOWN))


def build_opportunity_cost_context(consideration):
    """`products/opportunity_cost.html`이 그대로 쓸 컨텍스트를 만듭니다.

    대안이 아직 없으면(`status = DRAFT`) 두 목록 모두 빈 리스트입니다.
    템플릿이 빈 상태를 렌더하므로 여기서 에러를 내지 않습니다.
    """
    alternatives = (
        Alternative.objects.filter(
            consideration=consideration,
            is_current=True,
        )
        .select_related("category", "item")
        .order_by("category__display_order", "category_id", "slot")
    )

    bars = []
    financial_costs = []

    for alternative in alternatives:
        item = alternative.item

        if alternative.result_type == Alternative.ResultType.QUANTITY:
            color, text_color = BAR_PALETTE[len(bars) % len(BAR_PALETTE)]
            quantity = alternative.equivalent_quantity

            bars.append(
                {
                    "alternative_id": alternative.id,
                    "category_name": alternative.category.name,
                    "name": item.name,
                    # JS가 블록을 쌓을 때 쓰는 실제 비율입니다. 표시용
                    # display_count와 달리 내림하지 않습니다.
                    "count": float(quantity),
                    "display_count": (
                        f"{format_quantity(quantity)}{item.unit_label}"
                    ),
                    "color": color,
                    "text_color": text_color,
                }
            )
        else:
            financial_costs.append(
                {
                    "alternative_id": alternative.id,
                    "category_name": alternative.category.name,
                    "name": item.name,
                    "display_text": alternative.display_text,
                    "expected_effect": alternative.expected_effect,
                }
            )

    return {
        "product_name": consideration.product_name,
        "product_price": format_price(consideration.product_price),
        "opportunity_costs": bars,
        "financial_costs": financial_costs,
    }
