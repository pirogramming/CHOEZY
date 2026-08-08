"""Gemini JSON 호출 공통 클라이언트.

응답 스키마를 지정해 호출하고 파싱된 dict를 돌려줍니다. 프롬프트 조립과
응답 검증은 각 앱의 `ai_service.py` / `services.py`가 맡습니다.
"""

import json

from django.conf import settings


class GeminiRequestError(RuntimeError):
    pass


class GeminiTimeoutError(GeminiRequestError):
    pass


def generate_json(prompt, response_schema, max_output_tokens=2048, temperature=0.2):
    if not settings.GEMINI_API_KEY:
        raise GeminiRequestError("GEMINI_API_KEY가 설정되지 않았습니다.")

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(
            api_key=settings.GEMINI_API_KEY,
            http_options=types.HttpOptions(
                timeout=settings.GEMINI_TIMEOUT_MS,
            ),
        )
        try:
            response = client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_json_schema=response_schema,
                    max_output_tokens=max_output_tokens,
                    temperature=temperature,
                ),
            )
        finally:
            client.close()
        if not response.text:
            raise GeminiRequestError("Gemini 응답이 비어 있습니다.")
        return json.loads(response.text)
    except GeminiRequestError:
        raise
    except Exception as exc:
        if "timeout" in type(exc).__name__.lower():
            raise GeminiTimeoutError("Gemini 요청 시간이 초과되었습니다.") from exc
        raise GeminiRequestError("Gemini 요청에 실패했습니다.") from exc
