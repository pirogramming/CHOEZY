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
        return generate_json(prompt, RESPONSE_SCHEMA)
