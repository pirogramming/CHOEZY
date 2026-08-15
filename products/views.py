from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.generic import CreateView

from alternatives.visualization import build_opportunity_cost_context
from analyses.services import build_spending_stats

from .forms import ConsiderationForm
from .models import Consideration


class ConsiderationCreateView(LoginRequiredMixin, CreateView):
    """구매 고민 입력 (docs/API.md §5.1).

    JSON API가 아니라 폼 페이지입니다. 성공하면 대안 생성 페이지로
    리다이렉트하고, 실패하면 폼 에러가 렌더된 입력 화면을 그대로 돌려줍니다.
    """

    model = Consideration
    form_class = ConsiderationForm
    template_name = "products/consideration_form.html"

    def form_valid(self, form):
        form.instance.user = self.request.user
        form.instance.compare_criteria = list(
            Consideration.CompareCriterion.values
        )

        return super().form_valid(form)

    def get_success_url(self):
        return reverse(
            "alternatives:consideration_alternatives",
            kwargs={"pk": self.object.pk},
        )


@login_required
def comparison_table_view(request, pk):
    return render(
        request,
        "products/comparison_table.html",
        {
            "consideration_id": pk,
        },
    )


@login_required
def opportunity_cost_view(request, pk):
    """현재 사용자의 구매 고민에 대한 기회비용 시각화 페이지입니다."""
    consideration = get_object_or_404(
        Consideration,
        pk=pk,
        user=request.user,
    )
    context = build_opportunity_cost_context(consideration)
    context["consideration_id"] = consideration.pk

    return render(
        request,
        "products/opportunity_cost.html",
        context,
    )

@login_required
def consumption_log(request):
    return render(request, "products/consumption_log.html")


def _percentages(counts):
    total = sum(counts)
    if not total:
        return [0] * len(counts)
    ratios = [round(c * 100 / total) for c in counts]
    gap = 100 - sum(ratios)
    if gap:
        largest = max(range(len(ratios)), key=lambda i: counts[i])
        ratios[largest] += gap
    return ratios


def _build_insight_message(stats, purpose_labels):
    if not stats["total_count"]:
        return "아직 소비 기록이 없어요. 첫 소비 기록을 남겨보세요!"

    highest = stats["highest_satisfaction_purpose"]
    lowest = stats["lowest_satisfaction_purpose"]

    if highest and lowest and highest["purpose"] != lowest["purpose"]:
        highest_label = purpose_labels.get(highest["purpose"], highest["purpose"] or "기타")
        lowest_label = purpose_labels.get(lowest["purpose"], lowest["purpose"] or "기타")
        return (
            f"{highest_label} 목적의 소비 만족도가 가장 높고({highest['average_satisfaction']}점), "
            f"{lowest_label} 목적의 소비는 다시 한 번 생각해보는 게 좋겠어요"
            f"({lowest['average_satisfaction']}점)."
        )

    if highest:
        highest_label = purpose_labels.get(highest["purpose"], highest["purpose"] or "기타")
        return f"{highest_label} 목적의 소비 만족도가 {highest['average_satisfaction']}점으로 가장 높아요."

    return "목적이 분명한 소비일수록 만족도가 높고, 신중하게 비교한 후 구매하는 경향이 있어요"


DONUT_COLOR_PALETTE = ["#93B686", "#BFDCB4", "#C9C3BC", "#E3EEDD"]


@login_required
def choezy_report(request):
    stats = build_spending_stats(request.user)
    purpose_labels = dict(Consideration.Purpose.choices)

    purpose_rows = sorted(stats["by_purpose"], key=lambda p: -p["count"])
    top_rows = purpose_rows[:3]
    rest_rows = purpose_rows[3:]

    names = [
        purpose_labels.get(row["purpose"], row["purpose"] or "기타")
        for row in top_rows
    ]
    counts = [row["count"] for row in top_rows]

    if rest_rows:
        names.append("기타")
        counts.append(sum(row["count"] for row in rest_rows))

    other_details = [
        {
            "name": purpose_labels.get(
                row["purpose"],
                row["purpose"] or "기타",
            ),
            "count": row["count"],
        }
        for row in rest_rows
    ]

    ratios = _percentages(counts)
    colored_slices = [
        {"name": name, "ratio": ratio, "color": DONUT_COLOR_PALETTE[i % len(DONUT_COLOR_PALETTE)]}
        for i, (name, ratio) in enumerate(zip(names, ratios))
    ]

    gradient_parts = []
    cum = 0
    for slice_data in colored_slices:
        start = cum
        cum += slice_data["ratio"]
        slice_data["start"] = start
        slice_data["end"] = cum
        gradient_parts.append(f"{slice_data['color']} {start}% {cum}%")
    donut_gradient = (
        "conic-gradient(" + ", ".join(gradient_parts) + ")"
        if gradient_parts
        else "conic-gradient(#eee 0% 100%)"
    )

    top_purpose = colored_slices[0] if colored_slices else None
    highest = stats["highest_satisfaction_purpose"]
    lowest = stats["lowest_satisfaction_purpose"]
    has_distinct_lowest = (
        lowest is not None
        and (
            highest is None
            or lowest["purpose"] != highest["purpose"]
        )
    )

    stat_cards = [
        {
            "icon": "category",
            "label": "가장 많이 소비하는 분야",
            "value": (
                f"{top_purpose['name']} 목적의 소비가 {top_purpose['ratio']}%"
                if top_purpose
                else "아직 소비 기록이 없어요"
            ),
        },
        {
            "icon": "target",
            "label": "구매 확정 비율",
            "value": f"확정 구매가 {stats['purchase_rate']}%",
        },
        {
            "icon": "heart",
            "label": "만족도가 높은 소비",
            "value": (
                f"{purpose_labels.get(highest['purpose'], highest['purpose'])} "
                f"만족도가 {highest['average_satisfaction']}점"
                if highest
                else "아직 데이터가 없어요"
            ),
        },
        {
            "icon": "refresh",
            "label": "다시 생각해볼 소비",
            "value": (
                f"{purpose_labels.get(lowest['purpose'], lowest['purpose'])} "
                f"만족도가 {lowest['average_satisfaction']}점"
                if has_distinct_lowest
                else "비교할 다른 구매 목적 데이터가 없어요"
            ),
        },
    ]

    report_data = {
        "total_count": stats["purchased_count"],
        "top3": colored_slices,
        "other_slice": next(
            (
                slice_data
                for slice_data in colored_slices
                if slice_data["name"] == "기타"
            ),
            None,
        ),
        "other_details": other_details,
        "donut_gradient": donut_gradient,
        "insight_message": _build_insight_message(stats, purpose_labels),
        "stats": stat_cards,
    }

    return render(
        request,
        "products/choezy_report.html",
        {"report_data": report_data},
    )
