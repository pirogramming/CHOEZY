"""AI 구매 의사결정 Gemini 연동 (docs/API.md §8.1).

AI는 3단계 등급(HIGH/MIDDLE/LOW)과 문장만 만듭니다. 가격·기회비용 숫자는
이미 `Alternative`에 계산되어 있으므로 프롬프트에 넣어 근거로만 쓰게 하고,
AI가 새 숫자를 만들지 않도록 응답 스키마에서 제외합니다.
"""

from core.gemini import (
    GeminiRequestError,
    GeminiTimeoutError,
    generate_json,
)

from .models import DECISION_KEY_POINT_COUNT, Decision


__all__ = [
    "GeminiDecisionAdvisor",
    "GeminiRequestError",
    "GeminiTimeoutError",
    "RESPONSE_SCHEMA",
]


RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "purpose_fit": {"type": "string", "enum": list(Decision.Level.values)},
        "expected_satisfaction": {
            "type": "string",
            "enum": list(Decision.Level.values),
        },
        "recommendation": {
            "type": "string",
            "enum": list(Decision.Level.values),
        },
        "key_points": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": DECISION_KEY_POINT_COUNT,
            "maxItems": DECISION_KEY_POINT_COUNT,
        },
        "summary": {"type": "string"},
    },
    "required": [
        "purpose_fit",
        "expected_satisfaction",
        "recommendation",
        "key_points",
        "summary",
    ],
}


class GeminiDecisionAdvisor:
    def advise(self, prompt):
        return generate_json(prompt, RESPONSE_SCHEMA, max_output_tokens=1024)
