# Event type -> UI/DB category 매핑 유틸
# (danger/caution/alert) <-> (warning/caution/daily)

from __future__ import annotations

EVENT_TYPE_TO_CATEGORY: dict[str, str] = {
    "danger": "warning",
    "caution": "caution",
    "alert": "daily",
}


def event_type_to_category(event_type: str | None, default: str = "daily") -> str:
    if not event_type:
        return default
    return EVENT_TYPE_TO_CATEGORY.get(event_type, default)

