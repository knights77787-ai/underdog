"""이벤트 피드백 API."""
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from App.db.crud import feedback as crud_feedback
from App.db.database import get_db

router = APIRouter(prefix="/feedback", tags=["feedback"])


class FeedbackBody(BaseModel):
    event_id: int = Field(..., description="피드백 대상 이벤트 ID")
    vote: Literal["up", "down"] = Field(..., description="up=정탐, down=오탐")
    comment: Optional[str] = Field(None, max_length=255, description="한줄 코멘트")
    client_session_uuid: Optional[str] = Field(None, description="게스트 세션 식별용")


@router.post("")
def post_feedback(
    db: Session = Depends(get_db),
    body: FeedbackBody = ...,
):
    """
    이벤트에 대한 피드백 저장.
    로그인 유저는 추후 user_id 연동, 현재는 client_session_uuid 또는 비로그인으로 저장.
    """
    try:
        row = crud_feedback.create_feedback(
            db,
            event_id=body.event_id,
            vote=body.vote,
            comment=body.comment,
            user_id=None,
            client_session_uuid=body.client_session_uuid,
        )
        return {
            "ok": True,
            "feedback_id": row.feedback_id,
            "event_id": row.event_id,
            "vote": row.vote,
            "comment": row.comment if row.comment is not None else "",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
