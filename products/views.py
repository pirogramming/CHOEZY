from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, render
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

        return super().form_valid(form)

    def get_success_url(self):
        # alternatives 페이지가 아직 없어 URL 이름 대신 경로를 직접 씁니다.
        return f"/alternatives/considerations/{self.object.pk}/"


def comparison_table_view(request, pk):

    return render(
        request,
        "products/comparison_table.html",
        {
            "consideration_id": pk,
        }
    )


@login_required
def opportunity_cost_view(request, pk):
    """기회비용 시각화 페이지 (docs/API.md §7).

    비교표 페이지와 달리 JS가 API를 부르지 않습니다. 막대 높이·색·표기까지
    전부 서버에서 확정해 컨텍스트로 내려줍니다 (§2.10).

    남의 고민은 404입니다 — 403으로 돌려주면 "그 id는 존재한다"는 사실이
    새어 나갑니다.
    """
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
