"""사용자 등록 STT 키워드 (실시간 판정에 병합)."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from App.db.crud import user_custom_keywords as crud_uw
from App.db.database import get_db
from App.WS import handlers as ws_handlers

router = APIRouter(prefix="/user-keywords", tags=["user-keywords"])


class UserKeywordPayload(BaseModel):
    phrase: str = Field(..., min_length=1, max_length=255)
    event_type: Literal["danger", "caution", "alert"]


_ERR_MSG = {
    "invalid_event_type": "알림 분류가 올바르지 않습니다.",
    "empty_phrase": "키워드를 입력해 주세요.",
    "phrase_too_long": "키워드는 255자 이하여야 합니다.",
    "duplicate_phrase": "이미 등록된 키워드입니다.",
    "not_found": "해당 키워드를 찾을 수 없거나 권한이 없습니다.",
}


@router.get("")
def list_user_keywords(
    session_id: str = Query(..., description="클라이언트 세션 문자열"),
    db: Session = Depends(get_db),
):
    data = crud_uw.list_keywords_json(db, session_id)
    return {"ok": True, "count": len(data), "data": data}


@router.post("")
def add_user_keyword(
    body: UserKeywordPayload,
    session_id: str = Query(..., description="클라이언트 세션 문자열"),
    db: Session = Depends(get_db),
):
    try:
        row = crud_uw.create_user_custom_keyword(
            db, session_id, body.phrase, body.event_type
        )
    except ValueError as e:
        key = str(e) or "invalid_event_type"
        raise HTTPException(400, _ERR_MSG.get(key, "등록에 실패했습니다."))
    ws_handlers.invalidate_user_keyword_cache(session_id)
    return {
        "ok": True,
        "data": {
            "user_custom_keyword_id": row.user_custom_keyword_id,
            "phrase": row.phrase,
            "event_type": row.event_type,
        },
    }


@router.patch("/{keyword_id}")
def update_user_keyword(
    keyword_id: int,
    body: UserKeywordPayload,
    session_id: str = Query(..., description="클라이언트 세션 문자열"),
    db: Session = Depends(get_db),
):
    try:
        row = crud_uw.update_user_custom_keyword(
            db, session_id, keyword_id, body.phrase, body.event_type
        )
    except ValueError as e:
        key = str(e) or "invalid_event_type"
        if key == "not_found":
            raise HTTPException(404, _ERR_MSG["not_found"])
        raise HTTPException(400, _ERR_MSG.get(key, "수정에 실패했습니다."))
    ws_handlers.invalidate_user_keyword_cache(session_id)
    return {
        "ok": True,
        "data": {
            "user_custom_keyword_id": row.user_custom_keyword_id,
            "phrase": row.phrase,
            "event_type": row.event_type,
        },
    }


@router.delete("/{keyword_id}")
def remove_user_keyword(
    keyword_id: int,
    session_id: str = Query(..., description="클라이언트 세션 문자열"),
    db: Session = Depends(get_db),
):
    ok = crud_uw.delete_user_custom_keyword(db, session_id, keyword_id)
    if not ok:
        raise HTTPException(404, _ERR_MSG["not_found"])
    ws_handlers.invalidate_user_keyword_cache(session_id)
    return {"ok": True}
