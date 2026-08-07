from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse
from django.views.generic import CreateView

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

from django.shortcuts import render


def comparison_table_view(request, pk):

    return render(
        request,
        "products/comparison_table.html",
        {
            "consideration_id": pk,
        }
    )

from django.shortcuts import render


def opportunity_cost_view(request, pk):

    return render(
        request,
        "products/opportunity_cost.html",
        {
            "consideration_id": pk
        }
    )


# 기회비용 시각화 페이지 UI 확인용 임시 데이터 (추후 삭제 요망)
def opportunity_cost_view(request, pk):


    opportunity_costs = [


        {
            "name": "온라인<br>강의",
            "count": 10,
            "display_count": "10개",
            "color": "pink",
            "text_color": "pink-text",
        },


        {
            "name": "헬스장<br>12개월",
            "count": 1.4,
            "display_count": "1.4개월",
            "color": "yellow",
            "text_color": "yellow-text",
        },


        {
            "name": "전시회<br>관람 1회",
            "count": 29.7,
            "display_count": "29.7회",
            "color": "orange",
            "text_color": "orange-text",
        },


        {
            "name": "일본 3박 4일<br>여행",
            "count": 1.2,
            "display_count": "1.2회",
            "color": "travel",
            "text_color": "pink-text",
        },


    ]


    return render(
        request,
        "products/opportunity_cost.html",
        {
            "consideration_id": pk,
            "product_price": "220만원",
            "opportunity_costs": opportunity_costs,
        }
    )
