"""로그 조회 라우트 (마일스톤 5, REST: /logs). DB에서 조회."""
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from App.Core.config import MAX_LOG_LIMIT
from App.db.crud import events as crud_events
from App.db.database import get_db

LogType = Literal["all", "caption", "alert"]

router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("")
def get_logs(
    db: Session = Depends(get_db),
    type: LogType = Query("all", description="all | caption | alert"),
    limit: int = Query(100, ge=1, le=500),
    session_id: Optional[str] = Query(None, description="특정 세션 ID"),
    since_ts_ms: Optional[int] = Query(None, description="이 값 이상 ts_ms만 (하한)"),
    until_ts_ms: Optional[int] = Query(None, description="이 값 이하 ts_ms만 (상한)"),
):
    limit = min(limit, MAX_LOG_LIMIT)
    items = crud_events.get_logs_from_db(
        db, log_type=type, limit=limit,
        session_id=session_id,
        since_ts_ms=since_ts_ms,
        until_ts_ms=until_ts_ms,
    )
    return {
        "ok": True,
        "type": type,
        "session_id": session_id,
        "limit": limit,
        "count": len(items),
        "data": items,
    }
