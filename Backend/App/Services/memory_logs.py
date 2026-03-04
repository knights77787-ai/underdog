"""메모리 로그 저장소 (마일스톤 5: caption/alert 최근 N건).

ts 스키마는 모두 number(ms)로 통일: ts_ms.
프로젝트 전체에서 import: from App.Services.memory_logs import memory_logs
"""
from collections import deque
from time import time

from App.Core.config import MAX_ALERTS, MAX_CAPTIONS

captions_log: deque = deque(maxlen=MAX_CAPTIONS)
alerts_log: deque = deque(maxlen=MAX_ALERTS)


def _now_ms() -> int:
    return int(time() * 1000)


def append_caption(session_id: str, text: str, ts_ms: int | None = None) -> dict:
    entry = {
        "type": "caption",
        "session_id": session_id,
        "text": text,
        "ts_ms": ts_ms if ts_ms is not None else _now_ms(),
    }
    captions_log.append(entry)
    return entry


def append_alert(
    session_id: str,
    text: str,
    keyword: str,
    event_type: str,
    category: str,
    score: float,
    ts_ms: int | None = None,
    source: str = "text",
) -> dict:
    """source: 'text'(키워드) | 'audio'(YAMNet) | 'demo'(데모 트리거)."""
    entry = {
        "type": "alert",
        "source": source,
        "category": category,
        "event_type": event_type,
        "keyword": keyword,
        "text": text,
        "session_id": session_id,
        "ts_ms": ts_ms if ts_ms is not None else _now_ms(),
        "score": score,
    }
    alerts_log.append(entry)
    return entry


def get_captions(limit: int, session_id: str | None = None) -> list:
    source = list(captions_log)
    if session_id:
        source = [e for e in source if e.get("session_id") == session_id]
    return list(source)[-limit:][::-1]


def get_alerts(limit: int, session_id: str | None = None) -> list:
    source = list(alerts_log)
    if session_id:
        source = [e for e in source if e.get("session_id") == session_id]
    return list(source)[-limit:][::-1]


# A방식 통일: from App.Services.memory_logs import memory_logs
# (모듈 자체를 memory_logs로 노출해 한 인스턴스만 쓰도록)
import sys
memory_logs = sys.modules[__name__]
