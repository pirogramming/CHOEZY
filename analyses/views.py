from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from products.models import Consideration

from .models import Decision
from .serializers import serialize_decision


@login_required
def decision(request, pk):
    """AI 구매 의사결정 페이지 (docs/API.md §10).

    이미 만들어진 의사결정은 서버에서 렌더하고, 아직 없으면 화면에서
    `POST /api/analyses/considerations/<id>/decision/`을 호출합니다.
    """
    consideration = get_object_or_404(
        Consideration, pk=pk, user=request.user
    )
    result = Decision.objects.filter(consideration=consideration).first()
    return render(
        request,
        "analyses/comparison.html",
        {
            "consideration": consideration,
            "decision": result,
            "decision_data": serialize_decision(result) if result else None,
            "can_create_decision": (
                result is None
                and consideration.status == Consideration.Status.GENERATED
            ),
        },
    )
