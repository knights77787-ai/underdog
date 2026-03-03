"""관리자용 API: 요약, 최근 알림 리스트. DB에서 조회."""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from App.db.crud import events as crud_events
from App.db.database import get_db

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/summary")
def get_admin_summary(
    db: Session = Depends(get_db),
    session_id: Optional[str] = Query(None, description="특정 세션만 집계"),
    since_ts_ms: Optional[int] = Query(None),
    until_ts_ms: Optional[int] = Query(None),
    recent_window_sec: int = Query(300, ge=10, le=3600),
):
    summary = crud_events.get_admin_summary_from_db(
        db,
        session_id=session_id,
        since_ts_ms=since_ts_ms,
        until_ts_ms=until_ts_ms,
        recent_window_sec=recent_window_sec,
    )
    return {"ok": True, "summary": summary}


@router.get("/alerts")
def get_recent_alerts(
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=500),
    session_id: Optional[str] = Query(None),
    since_ts_ms: Optional[int] = Query(None),
    until_ts_ms: Optional[int] = Query(None),
):
    items = crud_events.get_logs_from_db(
        db, log_type="alert", limit=limit,
        session_id=session_id,
        since_ts_ms=since_ts_ms,
        until_ts_ms=until_ts_ms,
    )
    return {"ok": True, "limit": limit, "count": len(items), "data": items}
