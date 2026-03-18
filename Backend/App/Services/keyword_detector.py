"""
키워드 감지 서비스. Shared/constants/event_types.json 기준.
3단계: Warning(danger) / Caution / Daily(alert).
판정: judge()만 사용. danger → caution → alert 순 우선순위.
핫리로드: reload_keywords() 호출 시 파일 재읽기로 in-memory 갱신 (스레드 안전).
"""
import json
import logging
from threading import RLock
from typing import Literal

from App.Core.config import EVENT_TYPES_PATH

# event_type 순서: danger(Warning) 우선, caution, alert(Daily)
_EVENT_TYPE_ORDER: tuple[Literal["danger", "caution", "alert"], ...] = ("danger", "caution", "alert")
_RULE_LOCK = RLock()
_keyword_to_type: dict[str, Literal["danger", "caution", "alert"]] = {}
_keywords_by_type: dict[str, list[str]] = {}


def uniq(seq):
    """공백 제거 + 중복 제거 (순서 유지)."""
    seen = set()
    out = []
    for x in seq:
        x = (x or "").strip()
        if not x or x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out


def _load_rules_from_file() -> tuple[list[str], list[str], list[str]]:
    """event_types.json에서 keywords_by_event_type 기준으로 danger/caution/alert 리스트 반환."""
    if not EVENT_TYPES_PATH.exists():
        return [], [], []
    data = json.loads(EVENT_TYPES_PATH.read_text(encoding="utf-8"))
    kb = data.get("keywords_by_event_type", {})
    danger = kb.get("danger", []) or []
    caution = kb.get("caution", []) or []
    alert = kb.get("alert", []) or []
    return uniq(danger), uniq(caution), uniq(alert)


def _apply_loaded_rules(danger: list[str], caution: list[str], alert: list[str]) -> None:
    """로드된 리스트로 _keywords_by_type, _keyword_to_type 갱신 (lock 밖에서 호출 금지)."""
    global _keyword_to_type, _keywords_by_type
    _keywords_by_type = {"danger": list(danger), "caution": list(caution), "alert": list(alert)}
    _keyword_to_type = {}
    for etype in _EVENT_TYPE_ORDER:
        for kw in _keywords_by_type.get(etype, []):
            if kw in _keyword_to_type:
                if _keyword_to_type[kw] != etype:
                    logging.getLogger(__name__).warning(
                        "event_types.json: keyword %r already mapped to %r, skipping %r",
                        kw, _keyword_to_type[kw], etype,
                    )
                continue
            _keyword_to_type[kw] = etype


def reload_keywords() -> dict:
    """event_types.json을 다시 읽어 in-memory를 갱신. 스레드 안전, 결과 요약 반환."""
    danger, caution, alert = _load_rules_from_file()
    with _RULE_LOCK:
        _apply_loaded_rules(danger, caution, alert)
    return {
        "ok": True,
        "warning_count": len(danger),
        "caution_count": len(caution),
        "daily_count": len(alert),
        "path": str(EVENT_TYPES_PATH),
    }


def get_keyword_counts() -> dict:
    """현재 로드된 키워드 개수 (스레드 안전)."""
    with _RULE_LOCK:
        return {
            "warning_count": len(_keywords_by_type.get("danger", [])),
            "caution_count": len(_keywords_by_type.get("caution", [])),
            "daily_count": len(_keywords_by_type.get("alert", [])),
        }


# 서버 시작 시 1회 로드
reload_keywords()


def get_keyword_to_type() -> dict[str, Literal["danger", "caution", "alert"]]:
    with _RULE_LOCK:
        return dict(_keyword_to_type)


def judge(
    text: str,
) -> tuple[str, str, str | None, float]:
    """
    판정 우선순위: Warning(danger) → Caution → Daily(alert) → info.
    반환: (category, event_type, keyword, score). category는 warning|caution|daily.
    """
    text = text or ""
    with _RULE_LOCK:
        danger_list = list(_keywords_by_type.get("danger", []))
        caution_list = list(_keywords_by_type.get("caution", []))
        alert_list = list(_keywords_by_type.get("alert", []))
    for kw in danger_list:
        if kw in text:
            return ("warning", "danger", kw, 1.0)
    for kw in caution_list:
        if kw in text:
            return ("caution", "caution", kw, 0.85)
    for kw in alert_list:
        if kw in text:
            return ("daily", "alert", kw, 0.7)
    return ("daily", "info", None, 0.2)
