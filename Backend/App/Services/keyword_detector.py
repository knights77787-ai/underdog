"""
키워드 감지 서비스. Shared/constants/event_types.json 기준 (ERD event_type: danger | alert).
판정: judge()만 사용. danger(warning) 우선, 없으면 alert(daily), 둘 다 아니면 info(알림 없음).
쿨다운은 handlers에서 (session_id, keyword, event_type) 기준으로 적용.
핫리로드: reload_keywords() 호출 시 파일 재읽기로 in-memory 갱신 (스레드 안전).
"""
import json
import logging
from threading import RLock
from typing import Literal

from app.Core.config import EVENT_TYPES_PATH

# event_type 순서: danger(경고) 우선, 그 다음 alert(일상)
_EVENT_TYPE_ORDER: tuple[Literal["danger", "alert"], ...] = ("danger", "alert")
_RULE_LOCK = RLock()
_keyword_to_type: dict[str, Literal["danger", "alert"]] = {}
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


def _load_rules_from_file() -> tuple[list[str], list[str]]:
    """event_types.json에서 keywords_by_event_type 기준으로 danger/alert 리스트 반환."""
    if not EVENT_TYPES_PATH.exists():
        return [], []
    data = json.loads(EVENT_TYPES_PATH.read_text(encoding="utf-8"))
    kb = data.get("keywords_by_event_type", {})
    danger = kb.get("danger", []) or []
    alert = kb.get("alert", []) or []
    return uniq(danger), uniq(alert)


def _apply_loaded_rules(danger: list[str], alert: list[str]) -> None:
    """로드된 리스트로 _keywords_by_type, _keyword_to_type 갱신 (lock 밖에서 호출 금지)."""
    global _keyword_to_type, _keywords_by_type
    _keywords_by_type = {"danger": list(danger), "alert": list(alert)}
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
    danger, alert = _load_rules_from_file()
    with _RULE_LOCK:
        _apply_loaded_rules(danger, alert)
    return {
        "ok": True,
        "warning_count": len(danger),
        "daily_count": len(alert),
        "path": str(EVENT_TYPES_PATH),
    }


def get_keyword_counts() -> dict:
    """현재 로드된 키워드 개수 (스레드 안전)."""
    with _RULE_LOCK:
        return {
            "warning_count": len(_keywords_by_type.get("danger", [])),
            "daily_count": len(_keywords_by_type.get("alert", [])),
        }


# 서버 시작 시 1회 로드
reload_keywords()


def get_keyword_to_type() -> dict[str, Literal["danger", "alert"]]:
    with _RULE_LOCK:
        return dict(_keyword_to_type)


def judge(
    text: str,
) -> tuple[str, str, str | None, float]:
    """
    판정 우선순위: warning(경고) → daily(일상) → info.
    반환: (category, event_type, keyword, score). keyword는 우선순위로 한 개만 반환.
    (예: 문장에 '불'+'도와' 둘 다 있어도 danger(불)만 반환. 다중 키워드 필요 시 judge_many() 확장.)
    쿨다운은 handlers에서 (session_id, keyword, event_type) 기준 적용.
    """
    text = text or ""
    with _RULE_LOCK:
        danger_list = list(_keywords_by_type.get("danger", []))
        alert_list = list(_keywords_by_type.get("alert", []))
    for kw in danger_list:
        if kw in text:
            return ("warning", "danger", kw, 1.0)
    for kw in alert_list:
        if kw in text:
            return ("daily", "alert", kw, 0.7)
    return ("daily", "info", None, 0.2)
