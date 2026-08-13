from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.generic import CreateView

from alternatives.visualization import build_opportunity_cost_context

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


@login_required
def choezy_report(request):
    top3 = [
        {"label": "여행", "percent": 38, "color": "#93B686"},
        {"label": "생활", "percent": 27, "color": "#BFDCB4"},
        {"label": "문화", "percent": 21, "color": "#C9C3BC"},
        {"label": "기타", "percent": 14, "color": "#E3EEDD"},
    ]

    gradient_parts = []
    cum = 0
    for item in top3:
        start = cum
        cum += item["percent"]
        gradient_parts.append(f"{item['color']} {start}% {cum}%")

    donut_gradient = "conic-gradient(" + ", ".join(gradient_parts) + ")"

    report_data = {
        "total_count": 38,
        "top3": top3,
        "donut_gradient": donut_gradient,
        "insight_message": "목적이 분명한 소비일수록 만족도가 높고, 신중하게 비교한 후 구매하는 경향이 있어요",
        "stats": [
            {"icon": "category", "label": "가장 많이 소비하는 분야", "value": "디지털 분야의 소비가 X%"},
            {"icon": "target", "label": "소비 목적", "value": "목적형 소비가 X%"},
            {"icon": "heart", "label": "만족도가 높은 소비", "value": "자기개발 만족도가 X점"},
            {"icon": "refresh", "label": "다시 생각해볼 소비", "value": "일상/편의 만족도가 X점"},
        ],
    }

    return render(
        request,
        "products/choezy_report.html",
        {"report_data": report_data},
    )