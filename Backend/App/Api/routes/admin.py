"""관리자용 API: 요약, 최근 알림 리스트, 키워드 핫리로드. DB에서 조회."""
import time
from typing import Optional

import asyncio
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from App.Core.metrics import derived, snapshot
from App.Core.security import require_admin_token
from App.WS.handlers import AUDIOCLS_QUEUE, STT_QUEUE, _persist_alert
from App.WS.manager import manager
from App.db.crud import events as crud_events
from App.db.crud.feedback import list_feedback
from App.db.crud.feedback_reports import feedback_summary, feedback_suspects
from App.db.database import get_db
from App.Services.audio_rules import get_audio_rules_status, reload_audio_rules
from App.Services.keyword_detector import get_keyword_counts, reload_keywords

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin_token)],
)


@router.post("/reload-keywords")
def admin_reload_keywords():
    """키워드 룰 파일(event_types.json) 재로드. 서버 재시작 없이 적용."""
    result = reload_keywords()
    return {"ok": True, "message": "reloaded", "result": result}


@router.post("/reload-audio-rules")
def admin_reload_audio_rules():
    """오디오 룰(event_types.json audio_rules) 재로드. Yamnet 분류용."""
    return {"ok": True, "result": reload_audio_rules()}


@router.get("/audio-rules-status")
def admin_audio_rules_status():
    """현재 로드된 오디오 룰 상태(min_score, warning/daily 개수).
    event_types.json의 audio_rules는 index 기반: 로그의 YAMNET top=... 에서 top index 확인 후
    warning_indices / daily_indices 에 하나씩 추가하면 매핑됨."""
    return {"ok": True, **get_audio_rules_status()}


@router.get("/health")
def admin_health(request: Request, db: Session = Depends(get_db)):
    """DB·worker task·큐·룰 상태 종합. 시연 전 db_ok=True, task done=False면 정상."""
    db_ok = True
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_ok = False

    def task_state(t):
        if t is None:
            return {"exists": False, "done": None, "cancelled": None}
        return {"exists": True, "done": t.done(), "cancelled": t.cancelled()}

    stt_task = getattr(request.app.state, "stt_task", None)
    yamnet_task = getattr(request.app.state, "yamnet_task", None)
    tasks = {
        "stt": task_state(stt_task),
        "yamnet": task_state(yamnet_task),
    }

    queues = {
        "yamnet_qsize": AUDIOCLS_QUEUE.qsize(),
        "stt_qsize": STT_QUEUE.qsize(),
    }

    rules = {"audio_rules": get_audio_rules_status()}
    try:
        rules["keyword_rules"] = get_keyword_counts()
    except Exception:
        rules["keyword_rules"] = {"warning_count": None, "daily_count": None}

    return {
        "ok": True,
        "db_ok": db_ok,
        "tasks": tasks,
        "queues": queues,
        "metrics": snapshot(),
        "rules": rules,
    }


@router.get("/metrics")
def admin_metrics():
    """큐 크기·카운터·세션 수·평균 처리시간(ms) (운영/시연 모니터링). 토큰 보호됨."""
    m = derived()
    return {
        "ok": True,
        "queues": {
            "yamnet_queue_size": AUDIOCLS_QUEUE.qsize(),
            "stt_queue_size": STT_QUEUE.qsize(),
        },
        "counters": m,
        "sessions": {
            "session_count": len(manager.sessions),
        },
    }


@router.get("/keywords-status")
def admin_keywords_status():
    """현재 로드된 키워드 개수 확인."""
    return {"ok": True, **get_keyword_counts()}


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
    limit: int = Query(50, ge=1, le=500, description="한 번에 가져올 개수 (추천 50~100)"),
    session_id: Optional[str] = Query(None, description="특정 세션만 (선택)"),
    since_ts_ms: Optional[int] = Query(None, description="이 시간(ms) 이후만"),
    until_ts_ms: Optional[int] = Query(None, description="커서: 이 값보다 과거 알림만 (스크롤 더 불러오기 시 사용)"),
):
    result = crud_events.get_logs_from_db(
        db, log_type="alert", limit=limit,
        session_id=session_id,
        since_ts_ms=since_ts_ms,
        until_ts_ms=until_ts_ms,
    )
    items = result["items"]
    return {
        "ok": True,
        "limit": limit,
        "count": len(items),
        "data": items,
        "next_until_ts_ms": result["next_until_ts_ms"],
        "has_more": result["has_more"],
    }


@router.get("/feedback-summary")
def admin_feedback_summary(
    session_id: Optional[str] = Query(None),
    since_ts_ms: Optional[int] = Query(None),
    until_ts_ms: Optional[int] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """키워드·event_type별 up/down 집계 (down_rate 순)."""
    data = feedback_summary(
        db=db,
        session_id=session_id,
        since_ts_ms=since_ts_ms,
        until_ts_ms=until_ts_ms,
        limit=limit,
    )
    return {"ok": True, "count": len(data), "data": data}


@router.get("/feedback-suspects")
def admin_feedback_suspects(
    session_id: Optional[str] = Query(None),
    since_ts_ms: Optional[int] = Query(None),
    until_ts_ms: Optional[int] = Query(None),
    min_count: int = Query(5, ge=1, le=100),
    min_down_rate: float = Query(0.6, ge=0.0, le=1.0),
    limit: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """오탐 의심(Down 비율 높은) 키워드 후보. min_count·min_down_rate 이상만."""
    data = feedback_suspects(
        db=db,
        session_id=session_id,
        since_ts_ms=since_ts_ms,
        until_ts_ms=until_ts_ms,
        min_count=min_count,
        min_down_rate=min_down_rate,
        limit=limit,
    )
    return {"ok": True, "count": len(data), "data": data}


@router.get("/feedback")
def get_feedback_list(
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=500),
    session_id: Optional[str] = Query(None),
    event_id: Optional[int] = Query(None),
):
    """관리자: 피드백 목록 조회."""
    rows = list_feedback(db, limit=limit, session_id=session_id, event_id=event_id)
    return {
        "ok": True,
        "limit": limit,
        "count": len(rows),
        "data": [
            {
                "feedback_id": r.feedback_id,
                "event_id": r.event_id,
                "session_id": r.client_session_uuid,
                "vote": r.vote,
                "comment": r.comment,
            }
            for r in rows
        ],
    }


@router.post("/demo/emit")
async def admin_demo_emit(
    session_id: str = "S1",
    event_type: str = "danger",
    keyword: str = "demo",
    text: str = "DEMO EVENT",
):
    """데모 트리거: 현장 소리 인식이 흔들려도 한 번 눌러서 경고 이벤트 생성·브로드캐스트."""
    ts_ms = int(time.time() * 1000)
    kw = f"demo:{keyword}"
    event_id = await asyncio.to_thread(_persist_alert, session_id, text, kw, event_type, ts_ms)
    entry = {
        "type": "alert",
        "source": "demo",
        "event_type": event_type,
        "keyword": kw,
        "text": text,
        "session_id": session_id,
        "ts_ms": ts_ms,
        "score": 1.0,
    }
    if event_id is not None:
        entry["event_id"] = event_id
    await manager.broadcast_to_session(session_id, entry)
    return {"ok": True, "data": entry}
