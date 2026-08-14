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


DONUT_COLOR_PALETTE = ["#93B686", "#BFDCB4", "#C9C3BC", "#E3EEDD"]


@login_required
def choezy_report(request):
    stats = build_spending_stats(request.user)

    slices = stats["donut_slices"]
    colored_slices = [
        {**slice_data, "color": DONUT_COLOR_PALETTE[i % len(DONUT_COLOR_PALETTE)]}
        for i, slice_data in enumerate(slices)
    ]

    gradient_parts = []
    cum = 0
    for slice_data in colored_slices:
        start = cum
        cum += slice_data["ratio"]
        gradient_parts.append(f"{slice_data['color']} {start}% {cum}%")
    donut_gradient = (
        "conic-gradient(" + ", ".join(gradient_parts) + ")"
        if gradient_parts
        else "conic-gradient(#eee 0% 100%)"
    )

    top_category = stats["top_category"]
    highest = stats["highest_satisfaction_purpose"]
    lowest = stats["lowest_satisfaction_purpose"]
    purpose_labels = dict(Consideration.Purpose.choices)

    stat_cards = [
        {
            "icon": "category",
            "label": "가장 많이 소비하는 분야",
            "value": (
                f"{top_category['name']} 분야의 소비가 {top_category['ratio']}%"
                if top_category
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
                if lowest
                else "아직 데이터가 없어요"
            ),
        },
    ]

    report_data = {
        "total_count": stats["total_count"],
        "top3": colored_slices,
        "donut_gradient": donut_gradient,
        "insight_message": "목적이 분명한 소비일수록 만족도가 높고, 신중하게 비교한 후 구매하는 경향이 있어요",
        "stats": stat_cards,
    }

    return render(
        request,
        "products/choezy_report.html",
        {"report_data": report_data},
    )