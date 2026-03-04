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
