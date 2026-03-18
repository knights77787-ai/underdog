"""이벤트/자막 CRUD. caption·alert 저장 및 로그 조회."""
from typing import Literal

from sqlalchemy import desc
from sqlalchemy.orm import Session, joinedload

from App.db.crud import sessions as crud_sessions
from App.db.models import Event, EventTranscript, EventFeedback
from App.db.models import Session as SessionModel

LogType = Literal["all", "caption", "alert"]


def delete_events_older_than(db: Session, cutoff_ts_ms: int) -> int:
    """cutoff_ts_ms보다 오래된 이벤트 삭제 (event_feedback → event_transcripts → events 순).
    Returns: 삭제된 events 개수."""
    from datetime import datetime
    from sqlalchemy import delete, select, or_, and_
    cutoff_dt = datetime.utcfromtimestamp(cutoff_ts_ms / 1000.0)
    subq = select(Event.event_id).where(
        or_(
            Event.segment_start_ms < cutoff_ts_ms,
            and_(Event.segment_start_ms.is_(None), Event.created_at < cutoff_dt),
        )
    )
    to_delete = [r[0] for r in db.execute(subq).fetchall()]
    if not to_delete:
        return 0
    n = len(to_delete)
    db.execute(delete(EventFeedback).where(EventFeedback.event_id.in_(to_delete)))
    db.execute(delete(EventTranscript).where(EventTranscript.event_id.in_(to_delete)))
    db.execute(delete(Event).where(Event.event_id.in_(to_delete)))
    db.commit()
    return n


def _ts_ms_from_event(e: Event) -> int:
    if e.segment_start_ms is not None:
        return e.segment_start_ms
    return int(e.created_at.timestamp() * 1000) if e.created_at else 0


def _source_from_keyword(keyword: str | None) -> str:
    """keyword 접두어로 alert.source 추론 (DB에는 source 컬럼 없음)."""
    if not keyword:
        return "text"
    if keyword.startswith("demo:"):
        return "demo"
    if keyword.startswith("yamnet:"):
        return "audio"
    if keyword.startswith("custom:"):
        return "custom_sound"
    if keyword.startswith("phrase:"):
        return "custom_phrase"
    return "text"


def create_alert_event(
    db: Session,
    client_session_uuid: str,
    text: str,
    keyword: str,
    event_type: str,
    ts_ms: int,
    *,
    matched_custom_sound_id: int | None = None,
    custom_similarity: float | None = None,
) -> int:
    sess = crud_sessions.get_or_create_by_client_uuid(db, client_session_uuid)
    event = Event(
        session_id=sess.session_id,
        event_type=event_type,
        keyword=keyword,
        segment_start_ms=ts_ms,
        matched_custom_sound_id=matched_custom_sound_id,
        custom_similarity=custom_similarity,
    )
    try:
        db.add(event)
        db.flush()  # event_id 할당 (commit 전)
        transcript = EventTranscript(event_id=event.event_id, text=text)
        db.add(transcript)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return event.event_id  # flush() 후 이미 채워짐, refresh 불필요


def get_logs_from_db(
    db: Session,
    log_type: LogType,
    limit: int,
    session_id: str | None = None,
    since_ts_ms: int | None = None,
    until_ts_ms: int | None = None,
) -> dict:
    """스크롤(커서) 조회: 최신순 limit+1건 조회해 has_more 판단 후 limit건만 반환.

    Returns:
        {"items": [...], "next_until_ts_ms": int | None, "has_more": bool}
    """
    q = (
        db.query(Event)
        .options(joinedload(Event.session), joinedload(Event.transcripts))
    )
    if session_id is not None:
        q = q.join(Event.session).filter(SessionModel.client_session_uuid == session_id)
    if since_ts_ms is not None:
        q = q.filter(Event.segment_start_ms >= since_ts_ms)
    if until_ts_ms is not None:
        # 커서 기준: until_ts_ms \"미만\"만 가져와서 이전 페이지와 중복 방지
        q = q.filter(Event.segment_start_ms < until_ts_ms)
    if log_type == "caption":
        q = q.filter(Event.event_type == "pass")
    elif log_type == "alert":
        q = q.filter(Event.event_type.in_(["danger", "caution", "alert"]))

    # 정렬: ts_ms 내림차순 + event_id 내림차순(tie-breaker)으로 커서 안정성 확보
    events = q.order_by(desc(Event.segment_start_ms), desc(Event.event_id)).limit(limit + 1).all()
    has_more = len(events) > limit
    if has_more:
        events = events[:limit]

    out: list[dict] = []
    for event in events:
        ts_ms = _ts_ms_from_event(event)
        client_uuid = event.session.client_session_uuid if event.session else None
        text = event.transcripts[0].text if event.transcripts else ""
        if event.event_type == "pass":
            out.append({
                "type": "caption",
                "event_id": event.event_id,
                "session_id": client_uuid,
                "text": text,
                "ts_ms": ts_ms,
            })
        else:
            out.append({
                "type": "alert",
                "event_id": event.event_id,
                "source": _source_from_keyword(event.keyword),
                "event_type": event.event_type,
                "keyword": event.keyword or "",
                "session_id": client_uuid,
                "text": text,
                "ts_ms": ts_ms,
            })

    next_until_ts_ms = out[-1]["ts_ms"] if out else None
    return {"items": out, "next_until_ts_ms": next_until_ts_ms, "has_more": has_more}


def get_admin_summary_from_db(
    db: Session,
    session_id: str | None = None,
    since_ts_ms: int | None = None,
    until_ts_ms: int | None = None,
    recent_window_sec: int = 300,
) -> dict:
    import time

    q = db.query(Event).options(joinedload(Event.session), joinedload(Event.transcripts))
    if session_id is not None:
        q = q.join(Event.session).filter(SessionModel.client_session_uuid == session_id)
    if since_ts_ms is not None:
        q = q.filter(Event.segment_start_ms >= since_ts_ms)
    if until_ts_ms is not None:
        q = q.filter(Event.segment_start_ms <= until_ts_ms)

    events = q.all()
    now_ms = int(time.time() * 1000)
    cutoff = now_ms - (recent_window_sec * 1000)
    captions = [e for e in events if e.event_type == "pass"]
    alerts = [e for e in events if e.event_type in ("danger", "caution", "alert")]
    recent_alerts = [e for e in alerts if (e.segment_start_ms or 0) >= cutoff]
    session_ids = sorted(
        {e.session.client_session_uuid for e in events if e.session and e.session.client_session_uuid}
    )
    all_sorted = sorted(
        events,
        key=lambda e: (_ts_ms_from_event(e), 1 if e.event_type != "pass" else 0),
        reverse=True,
    )
    last_event = all_sorted[0] if all_sorted else None
    last_event_ts_ms = _ts_ms_from_event(last_event) if last_event else None

    def _last_event_dict(e: Event) -> dict | None:
        if not e:
            return None
        text = e.transcripts[0].text if e.transcripts else ""
        client_uuid = e.session.client_session_uuid if e.session else None
        if e.event_type == "pass":
            return {
                "type": "caption",
                "event_id": e.event_id,
                "session_id": client_uuid,
                "text": text,
                "ts_ms": _ts_ms_from_event(e),
            }
        return {
            "type": "alert",
            "event_id": e.event_id,
            "source": _source_from_keyword(e.keyword),
            "event_type": e.event_type,
            "keyword": e.keyword or "",
            "session_id": client_uuid,
            "text": text,
            "ts_ms": _ts_ms_from_event(e),
        }

    return {
        "session_id": session_id,
        "total_captions": len(captions),
        "total_alerts": len(alerts),
        "alerts_recent": {"window_sec": recent_window_sec, "count": len(recent_alerts), "since_ts_ms": cutoff},
        "unique_sessions": len(session_ids),
        "session_ids": session_ids[:50],
        "last_event_ts_ms": last_event_ts_ms,
        "last_event": _last_event_dict(last_event),
    }
