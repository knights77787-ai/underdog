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


def append_caption(session_id: str, text: str) -> dict:
    entry = {
        "type": "caption",
        "session_id": session_id,
        "text": text,
        "ts_ms": _now_ms(),
    }
    captions_log.append(entry)
    return entry


def append_alert(
    session_id: str,
    text: str,
    keyword: str,
    event_type: str,
) -> dict:
    entry = {
        "type": "alert",
        "event_type": event_type,
        "keyword": keyword,
        "session_id": session_id,
        "text": text,
        "ts_ms": _now_ms(),
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
