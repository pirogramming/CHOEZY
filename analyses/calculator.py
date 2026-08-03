from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN

from alternatives.models import Alternative, AlternativeItem


MAX_QUANTITY = Decimal("999999.99")


class CalculationError(ValueError):
    pass


@dataclass(frozen=True)
class CalculationResult:
    unit_price: int
    result_type: str
    equivalent_quantity: Decimal | None
    future_value: int | None
    duration: str
    expected_effect: str
    display_text: str


def _financial_params(item):
    params = item.calc_params
    period = params.get("period_month")
    rate = params.get("return_rate")
    if type(period) is not int or period <= 0:
        raise CalculationError("period_month는 0보다 큰 정수여야 합니다.")
    if isinstance(rate, bool) or not isinstance(rate, (int, float)):
        raise CalculationError("return_rate는 숫자여야 합니다.")
    if item.calc_type == AlternativeItem.CalcType.INVESTMENT:
        if not params.get("base_date"):
            raise CalculationError("투자 항목에는 base_date가 필요합니다.")
    return period, Decimal(str(rate)) / Decimal("100")


def is_calculable(item, product_price):
    try:
        calculate_opportunity_cost(item, product_price)
    except (CalculationError, ArithmeticError):
        return False
    return True


def calculate_opportunity_cost(item, product_price):
    principal = Decimal(product_price)
    if product_price <= 0:
        raise CalculationError("상품 가격은 0보다 커야 합니다.")

    if item.calc_type == AlternativeItem.CalcType.UNIT_PRICE:
        if item.average_price <= 0:
            raise CalculationError("대안 단가는 0보다 커야 합니다.")
        quantity = (principal / Decimal(item.average_price)).quantize(
            Decimal("0.01"), rounding=ROUND_DOWN
        )
        if quantity > MAX_QUANTITY:
            raise CalculationError("환산 수량이 저장 범위를 초과합니다.")
        shown = (
            str(int(quantity))
            if quantity >= 1
            else str(quantity.quantize(Decimal("0.1"), rounding=ROUND_DOWN))
        )
        return CalculationResult(
            unit_price=item.average_price,
            result_type=Alternative.ResultType.QUANTITY,
            equivalent_quantity=quantity,
            future_value=None,
            duration="",
            expected_effect="",
            display_text=f"{item.name} 약 {shown}{item.unit_label}",
        )

    period, rate = _financial_params(item)
    if item.calc_type == AlternativeItem.CalcType.SAVINGS:
        monthly = principal / Decimal(period)
        interest = (
            monthly
            * (rate / Decimal("12"))
            * Decimal(period * (period + 1))
            / Decimal("2")
        )
        future = principal + interest
    elif item.calc_type == AlternativeItem.CalcType.DEPOSIT:
        future = principal * (
            Decimal("1") + rate * Decimal(period) / Decimal("12")
        )
    elif item.calc_type == AlternativeItem.CalcType.INVESTMENT:
        future = principal * (Decimal("1") + rate)
    else:
        raise CalculationError("지원하지 않는 계산 유형입니다.")

    future_value = int(future.to_integral_value(rounding=ROUND_DOWN))
    amount_manwon = future_value // 10_000
    duration = f"{period}개월"
    if item.calc_type == AlternativeItem.CalcType.INVESTMENT:
        base_date = item.calc_params["base_date"]
        expected_effect = f"{base_date} 기준 약 {amount_manwon}만원"
        display_text = (
            f"{item.name} ({base_date} 기준) → 약 {amount_manwon}만원"
        )
    elif item.calc_type == AlternativeItem.CalcType.SAVINGS:
        monthly_amount = int(
            (principal / Decimal(period)).to_integral_value(
                rounding=ROUND_DOWN
            )
        )
        expected_effect = (
            f"월 {monthly_amount:,}원씩 {period}개월 → "
            f"약 {amount_manwon}만원"
        )
        display_text = (
            f"{item.name} {period}개월 → 약 {amount_manwon}만원"
        )
    else:
        expected_effect = f"{period}개월 뒤 약 {amount_manwon}만원"
        display_text = (
            f"{item.name} {period}개월 → 약 {amount_manwon}만원"
        )

    return CalculationResult(
        unit_price=product_price,
        result_type=Alternative.ResultType.FUTURE_VALUE,
        equivalent_quantity=None,
        future_value=future_value,
        duration=duration,
        expected_effect=expected_effect,
        display_text=display_text,
    )
