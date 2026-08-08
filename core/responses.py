"""JSON API 공통 응답 (docs/API.md §2.6)."""

from rest_framework.response import Response


def error_response(code, message, details=None, status=400):
    payload = {"error": {"code": code, "message": message}}
    if details:
        payload["error"]["details"] = details
    return Response(payload, status=status)


def service_error_response(exc):
    """서비스 레이어 예외를 §2.6 형식의 에러 응답으로 바꾼다."""
    return error_response(exc.code, exc.message, exc.details, exc.status_code)
