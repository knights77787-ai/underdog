"""로그 조회 CRUD (메모리 저장소 사용)."""
from typing import Literal

from app.Core.config import MAX_LOG_LIMIT
from app.Services.memory_logs import memory_logs


def get_logs(
    type_: Literal["caption", "alert", "all"],
    limit: int,
    session_id: str | None = None,
) -> dict:
    limit = min(limit, MAX_LOG_LIMIT)
    if type_ == "caption":
        return {"captions": memory_logs.get_captions(limit, session_id)}
    if type_ == "alert":
        return {"alerts": memory_logs.get_alerts(limit, session_id)}
    return {
        "captions": memory_logs.get_captions(limit, session_id),
        "alerts": memory_logs.get_alerts(limit, session_id),
    }
