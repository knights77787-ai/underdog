"""이벤트 피드백 API."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.crud.feedback import upsert_feedback
from app.db.database import get_db

router = APIRouter(prefix="/feedback", tags=["feedback"])


class FeedbackCreate(BaseModel):
    event_id: int = Field(..., ge=1, description="피드백 대상 이벤트 ID")
    session_id: str | None = Field(None, description="클라이언트 세션 문자열 예: S1")
    vote: str = Field(..., description="up | down")
    comment: str | None = Field(None, max_length=255)


@router.post("")
def create_feedback(
    payload: FeedbackCreate,
    db: Session = Depends(get_db),
):
    """이벤트 피드백 제출. 같은 (event_id, session_id)면 업데이트(덮어쓰기)."""
    try:
        row = upsert_feedback(
            db,
            event_id=payload.event_id,
            vote=payload.vote,
            comment=payload.comment,
            client_session_uuid=payload.session_id,
            user_id=None,
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
