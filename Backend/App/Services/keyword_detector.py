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
# phrase -> (event_type, canonical). canonical = sub-dict의 대표 키 (화재, 열차 등)
_phrase_to_result: dict[str, tuple[Literal["danger", "caution", "alert"], str]] = {}
# judge용: event_type 순서대로 (phrase, canonical) 리스트
_rules_flat: list[tuple[str, Literal["danger", "caution", "alert"], str]] = []


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


def _flatten_sub_dict(
    kb: dict,
) -> tuple[list[tuple[str, Literal["danger", "caution", "alert"], str]], int, int, int]:
    """sub-dict { canonical: [phrases] } 또는 flat list를 (phrase, event_type, canonical) 리스트로 변환."""
    out: list[tuple[str, Literal["danger", "caution", "alert"], str]] = []
    counts = [0, 0, 0]  # danger, caution, alert
    for i, etype in enumerate(_EVENT_TYPE_ORDER):
        val = kb.get(etype) or []
        if isinstance(val, dict):
            for canonical, phrases in val.items():
                for p in uniq(phrases if isinstance(phrases, list) else [phrases]):
                    if p:
                        out.append((p, etype, canonical))
                        counts[i] += 1
        else:
            for p in uniq(val if isinstance(val, list) else []):
                if p:
                    out.append((p, etype, p))
                    counts[i] += 1
    return out, counts[0], counts[1], counts[2]


def _load_rules_from_file() -> tuple[list[tuple[str, Literal["danger", "caution", "alert"], str]], int, int, int]:
    """event_types.json에서 keywords_by_event_type 로드. sub-dict 또는 flat list 지원."""
    if not EVENT_TYPES_PATH.exists():
        return [], 0, 0, 0
    data = json.loads(EVENT_TYPES_PATH.read_text(encoding="utf-8"))
    kb = data.get("keywords_by_event_type", {})
    return _flatten_sub_dict(kb)


def _apply_loaded_rules(
    rules: list[tuple[str, Literal["danger", "caution", "alert"], str]],
) -> None:
    """로드된 규칙으로 _phrase_to_result, _rules_flat 갱신 (lock 밖에서 호출 금지)."""
    global _phrase_to_result, _rules_flat
    _phrase_to_result = {}
    _rules_flat = []
    for phrase, etype, canonical in rules:
        if phrase in _phrase_to_result:
            prev_etype, prev_can = _phrase_to_result[phrase]
            if prev_etype != etype or prev_can != canonical:
                logging.getLogger(__name__).warning(
                    "event_types.json: phrase %r already mapped to %r/%r, skipping %r/%r",
                    phrase, prev_etype, prev_can, etype, canonical,
                )
            continue
        _phrase_to_result[phrase] = (etype, canonical)
        _rules_flat.append((phrase, etype, canonical))


def reload_keywords() -> dict:
    """event_types.json을 다시 읽어 in-memory를 갱신. 스레드 안전, 결과 요약 반환."""
    rules, dc, cc, ac = _load_rules_from_file()
    with _RULE_LOCK:
        _apply_loaded_rules(rules)
    return {
        "ok": True,
        "warning_count": dc,
        "caution_count": cc,
        "daily_count": ac,
        "path": str(EVENT_TYPES_PATH),
    }


def get_keyword_counts() -> dict:
    """현재 로드된 키워드 개수 (스레드 안전)."""
    with _RULE_LOCK:
        dc = sum(1 for _, e, _ in _rules_flat if e == "danger")
        cc = sum(1 for _, e, _ in _rules_flat if e == "caution")
        ac = sum(1 for _, e, _ in _rules_flat if e == "alert")
        return {
            "warning_count": dc,
            "caution_count": cc,
            "daily_count": ac,
        }


# 서버 시작 시 1회 로드
reload_keywords()


def get_keyword_to_type() -> dict[str, Literal["danger", "caution", "alert"]]:
    """phrase -> event_type (하위 호환용). canonical 대신 phrase로 매핑."""
    with _RULE_LOCK:
        return {p: e for p, e, _ in _rules_flat}


def judge(
    text: str,
) -> tuple[str, str, str | None, float]:
    """
    판정 우선순위: Warning(danger) → Caution → Daily(alert) → info.
    반환: (category, event_type, keyword, score). keyword는 canonical(대표 키).
    """
    text = text or ""
    # STT 결과에 "화 재"처럼 공백이 섞여 들어오는 케이스가 있어
    # 공백 제거 버전도 함께 검사한다.
    text_compact = "".join(text.split())
    with _RULE_LOCK:
<<<<<<< HEAD
        danger_list = list(_keywords_by_type.get("danger", []))
        caution_list = list(_keywords_by_type.get("caution", []))
        alert_list = list(_keywords_by_type.get("alert", []))
    for kw in danger_list:
        if kw in text or (text_compact and kw in text_compact):
            return ("warning", "danger", kw, 1.0)
    for kw in caution_list:
        if kw in text or (text_compact and kw in text_compact):
            return ("caution", "caution", kw, 0.85)
    for kw in alert_list:
        if kw in text or (text_compact and kw in text_compact):
            return ("daily", "alert", kw, 0.7)
=======
        rules = list(_rules_flat)
    scores = {"danger": 1.0, "caution": 0.85, "alert": 0.7}
    categories = {"danger": "warning", "caution": "caution", "alert": "daily"}
    for phrase, etype, canonical in rules:
        if phrase in text:
            return (categories[etype], etype, canonical, scores[etype])
>>>>>>> a6cd6d8187eaab221c6b6679c9faca81e904c641
    return ("daily", "info", None, 0.2)


def check_alerts(text: str):
    """텍스트에서 매칭되는 모든 (keyword, event_type) 쌍 반환. keyword는 canonical."""
    text = text or ""
    with _RULE_LOCK:
        rules = list(_rules_flat)
    seen: set[tuple[str, str]] = set()
    for phrase, etype, canonical in rules:
        if phrase in text:
            key = (canonical, etype)
            if key not in seen:
                seen.add(key)
                yield (canonical, etype)
