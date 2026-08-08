from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.responses import error_response, service_error_response

from .models import Decision
from .serializers import serialize_decision
from .services import DecisionServiceError, create_decision


class DecisionAPIView(APIView):
    """AI 의사결정 생성·조회 (docs/API.md §8.1, §8.2).

    MVP에서는 재생성을 제공하지 않습니다. 이미 있으면 409를 주고,
    프론트는 GET으로 기존 결과를 보여줍니다.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            decision = Decision.objects.get(
                consideration__pk=pk,
                consideration__user=request.user,
            )
        except Decision.DoesNotExist:
            return error_response(
                "NOT_FOUND", "AI 의사결정을 찾을 수 없습니다.", status=404
            )
        return Response(serialize_decision(decision))

    def post(self, request, pk):
        try:
            decision = create_decision(pk, request.user)
        except DecisionServiceError as exc:
            return service_error_response(exc)
        return Response(serialize_decision(decision), status=201)
