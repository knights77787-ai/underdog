"""이벤트 피드백 CRUD.

- vote 검증: up/down 만 허용
- event_id 존재 확인 후 저장
- 중복 정책: (event_id, user_id) 또는 (event_id, client_session_uuid) 당 1건, 있으면 업데이트
- commit 실패 시 rollback
"""
from sqlalchemy.orm import Session

from App.db.models import Event, EventFeedback


def create_feedback(
    db: Session,
    event_id: int,
    vote: str,
    comment: str | None = None,
    user_id: int | None = None,
    client_session_uuid: str | None = None,
) -> EventFeedback:
    """피드백 저장 또는 기존 건 업데이트. vote: 'up' | 'down'."""
    if vote not in ("up", "down"):
        raise ValueError("vote must be 'up' or 'down'")

    # event_id 존재 확인
    event = db.query(Event).filter(Event.event_id == event_id).first()
    if event is None:
        raise ValueError(f"event_id {event_id} not found")

    # 중복: (event_id, user_id) 또는 (event_id, client_session_uuid) 당 1회 → 있으면 업데이트
    existing = None
    if user_id is not None:
        existing = (
            db.query(EventFeedback)
            .filter(
                EventFeedback.event_id == event_id,
                EventFeedback.user_id == user_id,
            )
            .first()
        )
    elif client_session_uuid is not None:
        existing = (
            db.query(EventFeedback)
            .filter(
                EventFeedback.event_id == event_id,
                EventFeedback.client_session_uuid == client_session_uuid,
            )
            .first()
        )

    comment_val = (comment or "")[:255] if comment else None

    if existing is not None:
        existing.vote = vote
        existing.comment = comment_val
        try:
            db.commit()
            db.refresh(existing)
            return existing
        except Exception:
            db.rollback()
            raise

    row = EventFeedback(
        event_id=event_id,
        user_id=user_id,
        client_session_uuid=client_session_uuid,
        vote=vote,
        comment=comment_val,
    )
    try:
        db.add(row)
        db.commit()
        db.refresh(row)
        return row
    except Exception:
        db.rollback()
        raise
