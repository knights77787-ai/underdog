"""이벤트 피드백 CRUD.

- vote 검증: up/down 만 허용
- 중복 정책: (event_id, client_session_uuid) 당 1건, 있으면 업데이트(upsert)
- insert 시 IntegrityError(레이스) → rollback 후 재조회하여 update
"""
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from App.db.models import Event, EventFeedback


def upsert_feedback(
    db: Session,
    event_id: int,
    vote: str,
    comment: str | None = None,
    client_session_uuid: str | None = None,
    user_id: int | None = None,
) -> EventFeedback:
    """피드백 저장 또는 기존 건 업데이트. vote: 'up' | 'down'."""
    if vote not in ("up", "down"):
        raise ValueError("vote must be 'up' or 'down'")
    if comment is not None:
        comment = comment[:255]

    event = db.query(Event).filter(Event.event_id == event_id).first()
    if event is None:
        raise ValueError(f"event_id {event_id} not found")

    # 1) 기존 행 있으면 업데이트
    row = (
        db.query(EventFeedback)
        .filter(
            EventFeedback.event_id == event_id,
            EventFeedback.client_session_uuid == client_session_uuid,
        )
        .one_or_none()
    )
    if row is not None:
        row.vote = vote
        row.comment = comment
        if user_id is not None:
            row.user_id = user_id
        try:
            db.commit()
            db.refresh(row)
            return row
        except Exception:
            db.rollback()
            raise

    # 2) 없으면 insert (동시성 시 IntegrityError 처리)
    row = EventFeedback(
        event_id=event_id,
        vote=vote,
        comment=comment,
        client_session_uuid=client_session_uuid,
        user_id=user_id,
    )
    try:
        db.add(row)
        db.commit()
        db.refresh(row)
        return row
    except IntegrityError:
        db.rollback()
        existing = (
            db.query(EventFeedback)
            .filter(
                EventFeedback.event_id == event_id,
                EventFeedback.client_session_uuid == client_session_uuid,
            )
            .one()
        )
        existing.vote = vote
        existing.comment = comment
        if user_id is not None:
            existing.user_id = user_id
        try:
            db.commit()
            db.refresh(existing)
            return existing
        except Exception:
            db.rollback()
            raise


def list_feedback(
    db: Session,
    limit: int = 50,
    session_id: str | None = None,
    event_id: int | None = None,
) -> list[EventFeedback]:
    """피드백 목록 조회. session_id → client_session_uuid, event_id 필터."""
    q = db.query(EventFeedback)
    if session_id is not None:
        q = q.filter(EventFeedback.client_session_uuid == session_id)
    if event_id is not None:
        q = q.filter(EventFeedback.event_id == event_id)
    q = q.order_by(EventFeedback.feedback_id.desc())
    return q.limit(limit).all()


def list_feedback_admin(
    db: Session,
    limit: int = 50,
    session_id: str | None = None,
    event_id: int | None = None,
    event_type: str | None = None,
    vote: str | None = None,
    since_ts_ms: int | None = None,
    until_ts_ms: int | None = None,
) -> list:
    """관리자: 피드백 목록 조회. Event 조인하여 event_type, 날짜 필터.
    event_type: danger|caution|alert, vote: up|down"""
    from App.db.models import Event, EventTranscript

    q = (
        db.query(EventFeedback, Event)
        .join(Event, Event.event_id == EventFeedback.event_id)
    )
    if session_id is not None:
        q = q.filter(EventFeedback.client_session_uuid == session_id)
    if event_id is not None:
        q = q.filter(EventFeedback.event_id == event_id)
    if event_type is not None:
        q = q.filter(Event.event_type == event_type)
    if vote is not None:
        q = q.filter(EventFeedback.vote == vote)
    if since_ts_ms is not None:
        q = q.filter(Event.segment_start_ms >= since_ts_ms)
    if until_ts_ms is not None:
        q = q.filter(Event.segment_start_ms <= until_ts_ms)

    rows = q.order_by(EventFeedback.feedback_id.desc()).limit(limit).all()

    event_ids = [ev.event_id for _, ev in rows]
    texts_map = {}
    if event_ids:
        for et in db.query(EventTranscript).filter(EventTranscript.event_id.in_(event_ids)).all():
            if et.event_id not in texts_map:
                texts_map[et.event_id] = et.text

    out = []
    for fb, ev in rows:
        text = texts_map.get(ev.event_id, "")
        out.append({
            "feedback_id": fb.feedback_id,
            "event_id": fb.event_id,
            "keyword": ev.keyword,
            "event_type": ev.event_type,
            "text": text,
            "vote": fb.vote,
            "comment": fb.comment,
            "client_session_uuid": fb.client_session_uuid,
            "created_at": fb.created_at.isoformat() if fb.created_at else None,
            "segment_start_ms": ev.segment_start_ms,
        })
    return out
