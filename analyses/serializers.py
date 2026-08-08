"""AI 의사결정 직렬화 (docs/API.md §8.1).

화면에 그대로 출력할 문자열과 그래프 수치는 서버가 완성해서 내려보냅니다.
프론트가 `HIGH`/`MIDDLE`/`LOW`를 보고 라벨·막대 높이·색을 분기하지 않도록
`chart`에 담습니다. (§2.10)
"""

from django.utils import timezone

from .models import Decision


# 게이지 바늘 각도와 막대 높이에 쓰는 등급별 수치 (0~100)
LEVEL_SCORES = {
    Decision.Level.HIGH: 88,
    Decision.Level.MIDDLE: 55,
    Decision.Level.LOW: 32,
}

LEVEL_COLORS = {
    Decision.Level.HIGH: "#2ECC71",
    Decision.Level.MIDDLE: "#F4C430",
    Decision.Level.LOW: "#F5811F",
}

BAR_LABELS = [
    ("purpose_fit", "구매 목적 적합도"),
    ("expected_satisfaction", "예상 만족도"),
    ("recommendation", "추천도"),
]


def _bar(key, label, level):
    return {
        "key": key,
        "label": label,
        "level": level,
        "level_display": Decision.Level(level).label,
        "score": LEVEL_SCORES[level],
        "color": LEVEL_COLORS[level],
    }


def serialize_decision(decision):
    bars = [
        _bar(key, label, getattr(decision, key))
        for key, label in BAR_LABELS
    ]
    # 반원 게이지: 0도가 왼쪽 끝(낮음), 180도가 오른쪽 끝(높음)
    gauge = {**bars[0], "angle_deg": round(bars[0]["score"] * 1.8, 1)}
    return {
        "id": decision.id,
        "consideration_id": decision.consideration_id,
        "purpose_fit": decision.purpose_fit,
        "purpose_fit_display": decision.get_purpose_fit_display(),
        "expected_satisfaction": decision.expected_satisfaction,
        "expected_satisfaction_display": (
            decision.get_expected_satisfaction_display()
        ),
        "recommendation": decision.recommendation,
        "recommendation_display": decision.get_recommendation_display(),
        "key_points": list(decision.key_points),
        "summary": decision.summary,
        "ai_model": decision.ai_model,
        "created_at": timezone.localtime(decision.created_at).isoformat(),
        "chart": {"gauge": gauge, "bars": bars},
    }
