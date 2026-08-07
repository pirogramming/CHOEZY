from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from products.models import Consideration


def category_alternatives(request):
    return render(request, "alternatives/category_alternatives.html")


@login_required
def consideration_alternatives(request, pk):
    """현재 사용자의 구매 고민에 대한 카테고리별 대안 화면을 표시합니다."""
    consideration = get_object_or_404(
        Consideration,
        pk=pk,
        user=request.user,
    )
    return render(
        request,
        "alternatives/category_alternatives.html",
        {
            "consideration": consideration,
            "consideration_id": consideration.pk,
        },
    )
