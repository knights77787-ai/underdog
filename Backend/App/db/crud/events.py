"""이벤트/자막 CRUD. caption·alert 저장 및 로그 조회."""
from typing import Literal

from sqlalchemy import desc
from sqlalchemy.orm import Session, joinedload

from App.db.crud import sessions as crud_sessions
from App.db.models import Event, EventTranscript
from App.db.models import Session as SessionModel

LogType = Literal["all", "caption", "alert"]


def _ts_ms_from_event(e: Event) -> int:
    if e.segment_start_ms is not None:
        return e.segment_start_ms
    return int(e.created_at.timestamp() * 1000) if e.created_at else 0


def create_caption_event(
    db: Session,
    client_session_uuid: str,
    text: str,
    ts_ms: int,
) -> int:
    sess = crud_sessions.get_or_create_by_client_uuid(db, client_session_uuid)
    event = Event(session_id=sess.session_id, event_type="pass", segment_start_ms=ts_ms)
    db.add(event)
    db.flush()  # event_id 할당 (commit 전)
    transcript = EventTranscript(event_id=event.event_id, text=text)
    db.add(transcript)
    db.commit()
    db.refresh(event)
    return event.event_id


def create_alert_event(
    db: Session,
    client_session_uuid: str,
    text: str,
    keyword: str,
    event_type: str,
    ts_ms: int,
) -> int:
    sess = crud_sessions.get_or_create_by_client_uuid(db, client_session_uuid)
    event = Event(
        session_id=sess.session_id,
        event_type=event_type,
        keyword=keyword,
        segment_start_ms=ts_ms,
    )
    db.add(event)
    db.flush()  # event_id 할당 (commit 전)
    transcript = EventTranscript(event_id=event.event_id, text=text)
    db.add(transcript)
    db.commit()
    db.refresh(event)
    return event.event_id


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
        q = q.filter(Event.segment_start_ms <= until_ts_ms)
    if log_type == "caption":
        q = q.filter(Event.event_type == "pass")
    elif log_type == "alert":
        q = q.filter(Event.event_type.in_(["danger", "alert"]))

    events = q.order_by(desc(Event.segment_start_ms)).limit(limit + 1).all()
    has_more = len(events) > limit
    if has_more:
        events = events[:limit]

    out: list[dict] = []
    for event in events:
        ts_ms = _ts_ms_from_event(event)
        client_uuid = event.session.client_session_uuid if event.session else None
        text = event.transcripts[0].text if event.transcripts else ""
        if event.event_type == "pass":
            out.append({"type": "caption", "session_id": client_uuid, "text": text, "ts_ms": ts_ms})
        else:
            out.append({
                "type": "alert",
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
    alerts = [e for e in events if e.event_type in ("danger", "alert")]
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
            return {"type": "caption", "session_id": client_uuid, "text": text, "ts_ms": _ts_ms_from_event(e)}
        return {
            "type": "alert",
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
