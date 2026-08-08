from core.gemini import (
    GeminiRequestError,
    GeminiTimeoutError,
    generate_json,
)


__all__ = [
    "GeminiAlternativeSelector",
    "GeminiRequestError",
    "GeminiTimeoutError",
    "RESPONSE_SCHEMA",
]


RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "product_assessment": {
            "type": "object",
            "properties": {
                "duration": {"type": "string"},
                "expected_effect": {"type": "string"},
            },
            "required": ["duration", "expected_effect"],
        },
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
    def select(self, prompt):
        # 최대 3개 카테고리 × 대안 3개와 상품 평가를 한 번에 반환하므로,
        # 기본 2,048 토큰에서는 JSON이 중간에 잘릴 수 있습니다.
        return generate_json(
            prompt,
            RESPONSE_SCHEMA,
            max_output_tokens=8192,
        )
