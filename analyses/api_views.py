from django.core.paginator import Paginator
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.responses import error_response, service_error_response

from .models import Decision
from .serializers import (
    SpendingRecordFilterSerializer,
    SpendingRecordUpdateSerializer,
    SpendingRecordWriteSerializer,
    SpendingStatsFilterSerializer,
    serialize_decision,
    serialize_spending_pattern_report,
    serialize_spending_record,
    serialize_spending_record_item,
    serialize_spending_stats,
)
from .services import (
    DecisionServiceError,
    SpendingPatternServiceError,
    SpendingRecordServiceError,
    build_spending_stats,
    count_spending_records,
    create_decision,
    create_spending_pattern_report,
    create_spending_record,
    filter_spending_records,
    get_latest_spending_pattern_report,
    get_spending_record,
    update_spending_record,
)


def _validation_error(serializer):
    """DRF 검증 실패를 §2.6 형식으로 바꾼다."""
    return error_response(
        "VALIDATION_ERROR",
        "입력값을 확인해주세요.",
        serializer.errors,
        status=400,
    )


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


class SpendingRecordAPIView(APIView):
    """소비 기록 생성·조회·수정 (docs/API.md §8.5~§8.7).

    구매 의사결정 화면의 구매 결정 팝업이 POST를, 소비로그 상세 팝업이
    GET과 PATCH를 씁니다. POST 본문은 구매 상태와 만족도뿐이고 나머지
    필드는 서버가 채웁니다. (§8.4) PATCH는 여기에 목적을 더 받습니다 —
    상세 팝업에서 잘못 고른 목적을 고칠 수 있어야 합니다. (§8.7)
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            record = get_spending_record(pk, request.user)
        except SpendingRecordServiceError as exc:
            return service_error_response(exc)
        return Response(serialize_spending_record(record))

    def post(self, request, pk):
        serializer = SpendingRecordWriteSerializer(data=request.data)
        if not serializer.is_valid():
            return _validation_error(serializer)

        try:
            record = create_spending_record(
                pk,
                request.user,
                **serializer.validated_data,
            )
        except SpendingRecordServiceError as exc:
            return service_error_response(exc)

        return Response(serialize_spending_record(record), status=201)

    def patch(self, request, pk):
        serializer = SpendingRecordUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return _validation_error(serializer)

        try:
            record = update_spending_record(
                pk,
                request.user,
                **serializer.validated_data,
            )
        except SpendingRecordServiceError as exc:
            return service_error_response(exc)

        return Response(serialize_spending_record(record))


class SpendingRecordListAPIView(APIView):
    """소비로그 목록 (docs/API.md §8.8).

    상단 요약 카드는 이 응답에 없습니다. 집계는 통계 API(§8.9)에서
    따로 내려보냅니다.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = SpendingRecordFilterSerializer(data=request.query_params)
        if not serializer.is_valid():
            return _validation_error(serializer)

        filters = serializer.validated_data
        queryset = filter_spending_records(request.user, filters)

        paginator = Paginator(queryset, filters["page_size"])
        # 범위를 벗어난 page는 빈 목록으로 돌려줍니다. "더보기"를 연타해
        # 마지막 페이지를 넘겨도 404가 뜨지 않아야 합니다.
        page = paginator.get_page(min(filters["page"], paginator.num_pages))

        return Response(
            {
                "count": paginator.count,
                "page": page.number,
                "page_size": filters["page_size"],
                "has_next": page.has_next(),
                "results": [
                    serialize_spending_record_item(record)
                    for record in page.object_list
                ],
            }
        )


class SpendingStatsAPIView(APIView):
    """소비 기록 통계 (docs/API.md §8.9).

    소비로그 상단 요약 카드(`?month=2026-08`)와 초이지 리포트(전체 기간)가
    같은 응답을 씁니다.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = SpendingStatsFilterSerializer(data=request.query_params)
        if not serializer.is_valid():
            return _validation_error(serializer)

        stats = build_spending_stats(
            request.user,
            serializer.validated_data.get("month"),
        )
        return Response(serialize_spending_stats(stats))


class SpendingPatternAPIView(APIView):
    """소비 패턴 분석 생성·조회 (docs/API.md §8.10).

    초이지 리포트 상단의 AI 문장입니다. Gemini 호출이 수 초 걸리므로
    화면 진입 때는 GET으로 저장된 결과를 보여주고, 기록이 늘어 다시
    분석할 때만 POST를 부릅니다.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            report = get_latest_spending_pattern_report(request.user)
        except SpendingPatternServiceError as exc:
            return service_error_response(exc)

        return Response(
            serialize_spending_pattern_report(
                report, count_spending_records(request.user)
            )
        )

    def post(self, request):
        try:
            report = create_spending_pattern_report(request.user)
        except SpendingPatternServiceError as exc:
            return service_error_response(exc)

        return Response(
            serialize_spending_pattern_report(report, report.record_count),
            status=201,
        )
