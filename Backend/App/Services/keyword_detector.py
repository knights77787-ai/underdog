"""
키워드 감지 서비스. Shared/constants/event_types.json 기준 (ERD event_type: danger | alert).
쿨다운 적용 후 매칭된 키워드별 event_type 반환.
중복 키워드: 먼저 나온 타입 유지, 나중 건 경고 후 스킵.
"""
import json
import logging
import time
from pathlib import Path
from typing import Literal

from App.Core.config import EVENT_TYPES_PATH

COOLDOWN_SECONDS = 5
_keyword_to_type: dict[str, Literal["danger", "alert"]] = {}
_keyword_last_alert: dict[str, float] = {}


def _load_event_types() -> None:
    if not EVENT_TYPES_PATH.exists():
        return
    with open(EVENT_TYPES_PATH, encoding="utf-8") as f:
        data = json.load(f)
    global COOLDOWN_SECONDS
    COOLDOWN_SECONDS = data.get("keyword_cooldown_seconds", 5)
    keywords_by_type = data.get("keywords_by_event_type", {})
    for etype in ("danger", "alert"):
        for kw in keywords_by_type.get(etype, []):
            if kw in _keyword_to_type:
                if _keyword_to_type[kw] != etype:
                    logging.getLogger(__name__).warning(
                        "event_types.json: keyword %r already mapped to %r, skipping %r",
                        kw, _keyword_to_type[kw], etype,
                    )
                continue
            _keyword_to_type[kw] = etype


_load_event_types()


def get_keyword_to_type() -> dict[str, Literal["danger", "alert"]]:
    return _keyword_to_type


def check_alerts(text: str) -> list[tuple[str, Literal["danger", "alert"]]]:
    """
    텍스트에서 키워드 매칭 + 쿨다운 적용.
    반환: [(keyword, event_type), ...] (이번에 알림 낼 것만)
    """
    now = time.monotonic()
    result: list[tuple[str, Literal["danger", "alert"]]] = []
    for kw, etype in _keyword_to_type.items():
        if kw not in text:
            continue
        if _keyword_last_alert.get(kw, 0) + COOLDOWN_SECONDS > now:
            continue
        _keyword_last_alert[kw] = now
        result.append((kw, etype))
    return result
