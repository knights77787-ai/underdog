"""로그 조회 라우트 (마일스톤 5, REST: /logs)."""
from typing import Literal, Optional

from fastapi import APIRouter, Query

from App.Services.memory_logs import memory_logs

LogType = Literal["all", "caption", "alert"]

router = APIRouter(prefix="/logs", tags=["logs"])


def _pick_store(log_type: LogType) -> list[dict]:
    """로그 저장소 선택 (caption | alert | all)."""
    if log_type == "caption":
        return list(memory_logs.captions_log)
    if log_type == "alert":
        return list(memory_logs.alerts_log)
    # all
    return list(memory_logs.captions_log) + list(memory_logs.alerts_log)


@router.get("")
def get_logs(
    type: LogType = Query("all", description="all | caption | alert"),
    limit: int = Query(100, ge=1, le=500),
    session_id: Optional[str] = Query(None, description="특정 세션 ID"),
    since_ts_ms: Optional[int] = Query(
        None,
        description="이 값 이상 ts_ms만 (하한)",
    ),
    until_ts_ms: Optional[int] = Query(
        None,
        description="이 값 이하 ts_ms만 (상한)",
    ),
):
    """
    최근 로그 조회.

    - type: all | caption | alert
    - session_id: 특정 세션만
    - since_ts_ms / until_ts_ms: 시간 범위 필터
    - limit: 최근 N개
    """
    items = _pick_store(type)

    # 1) session_id 필터
    if session_id:
        items = [x for x in items if x.get("session_id") == session_id]

    # 2) 시간 필터 (ts_ms 기준)
    if since_ts_ms is not None:
        items = [x for x in items if int(x.get("ts_ms", 0)) >= since_ts_ms]
    if until_ts_ms is not None:
        items = [x for x in items if int(x.get("ts_ms", 0)) <= until_ts_ms]

    # 3) 시간 역순 정렬(최신 먼저) -> limit 개수만
    items = sorted(items, key=lambda x: int(x.get("ts_ms", 0)), reverse=True)
    items = items[:limit]

    return {
        "ok": True,
        "type": type,
        "session_id": session_id,
        "limit": limit,
        "count": len(items),
        "data": items,
    }
