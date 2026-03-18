"""이벤트 피드백 API."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from App.db.crud.feedback import upsert_feedback
from App.db.database import get_db
from App.db.models import Session as SessionModel

router = APIRouter(prefix="/feedback", tags=["feedback"])


class FeedbackCreate(BaseModel):
    event_id: int = Field(..., ge=1, description="피드백 대상 이벤트 ID")
    session_id: str | None = Field(None, description="클라이언트 세션 문자열 (client_session_uuid)")
    vote: str = Field(..., description="up | down")
    comment: str | None = Field(None, max_length=255)


def _get_user_id_from_session(db: Session, client_session_uuid: str | None) -> int | None:
    """client_session_uuid로 세션 조회 후 user_id 반환."""
    if not client_session_uuid:
        return None
    row = db.query(SessionModel).filter(
        SessionModel.client_session_uuid == client_session_uuid
    ).first()
    return row.user_id if row else None


@router.post("")
def create_feedback(
    payload: FeedbackCreate,
    db: Session = Depends(get_db),
):
    """이벤트 피드백 제출. 같은 (event_id, session_id)면 업데이트(덮어쓰기).
    vote=down 시 comment 필수. user_id는 세션에서 자동 조회."""
    if payload.vote not in ("up", "down"):
        raise HTTPException(status_code=400, detail="vote must be 'up' or 'down'")
    if payload.vote == "down" and (not payload.comment or not payload.comment.strip()):
        raise HTTPException(status_code=400, detail="vote=down 시 comment가 필요합니다.")

    user_id = _get_user_id_from_session(db, payload.session_id)
    try:
        row = upsert_feedback(
            db,
            event_id=payload.event_id,
            vote=payload.vote,
            comment=(payload.comment or "").strip() or None,
            client_session_uuid=payload.session_id,
            user_id=user_id,
        )
        return {
            "ok": True,
            "data": {
                "feedback_id": row.feedback_id,
                "event_id": row.event_id,
                "session_id": row.client_session_uuid,
                "vote": row.vote,
                "comment": row.comment,
            },
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
