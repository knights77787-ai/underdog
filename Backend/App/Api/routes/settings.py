"""설정 조회/저장 API. session_id(쿼리) = client_session_uuid."""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from App.db.crud import settings as crud_settings
from App.db.database import get_db

router = APIRouter(prefix="/settings", tags=["settings"])


class SettingsPatch(BaseModel):
    """저장 시 보낼 수 있는 필드. None이면 해당 키는 갱신하지 않음."""
    font_size: Optional[int] = Field(None, ge=10, le=60)
    alert_enabled: Optional[bool] = None
    event_save_enabled: Optional[bool] = None
    cooldown_sec: Optional[int] = Field(None, ge=0, le=60)
    auto_scroll: Optional[bool] = None


@router.get("")
def read_settings(
    db: Session = Depends(get_db),
    session_id: str = Query(..., description="클라이언트 세션 문자열 예: S1"),
):
    """해당 세션의 설정 조회. 없으면 기본값으로 생성 후 반환."""
    data = crud_settings.get_settings(db, session_id)
    return {"ok": True, "session_id": session_id, "data": data}


@router.post("")
def save_settings(
    payload: SettingsPatch,
    db: Session = Depends(get_db),
    session_id: str = Query(..., description="클라이언트 세션 문자열 예: S1"),
):
    """설정 일부만 보내면 기존 값에 merge해서 저장."""
    patch = payload.model_dump(exclude_none=True)
    data = crud_settings.upsert_settings(db, session_id, patch)
    return {"ok": True, "session_id": session_id, "data": data}
