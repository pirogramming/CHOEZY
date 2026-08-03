import json

from django.conf import settings


class GeminiRequestError(RuntimeError):
    pass


class GeminiTimeoutError(GeminiRequestError):
    pass


RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "selections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "category_code": {"type": "string"},
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "item_id": {"type": "integer"},
                                "slot": {"type": "integer"},
                                "duration": {"type": "string"},
                                "expected_effect": {"type": "string"},
                                "ai_reason": {"type": "string"},
                            },
                            "required": ["item_id", "slot", "ai_reason"],
                        },
                    },
                },
                "required": ["category_code", "items"],
            },
        }
    },
    "required": ["selections"],
}


class GeminiAlternativeSelector:
    model = settings.GEMINI_MODEL

    def select(self, prompt):
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
                    model=self.model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_json_schema=RESPONSE_SCHEMA,
                        max_output_tokens=2048,
                        temperature=0.2,
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
