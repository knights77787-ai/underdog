# App/db/crud/feedback_reports.py
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from typing import Optional

from App.db.models import EventFeedback, Event  # 너 모델명에 맞게(import 이름 다르면 수정)

def feedback_summary(
    db: Session,
    session_id: Optional[str] = None,
    since_ts_ms: Optional[int] = None,
    until_ts_ms: Optional[int] = None,
    limit: int = 50,
):
    """
    keyword(텍스트 키워드 or yamnet:xxx) + event_type(danger/alert) 별 up/down 집계
    """
    q = (
        db.query(
            Event.event_type.label("event_type"),
            Event.keyword.label("keyword"),  # 없으면 transcript text를 쓰게 바꿔도 됨
            func.count(EventFeedback.feedback_id).label("total"),
            func.sum(case((EventFeedback.vote == "up", 1), else_=0)).label("up_cnt"),
            func.sum(case((EventFeedback.vote == "down", 1), else_=0)).label("down_cnt"),
        )
        .join(EventFeedback, EventFeedback.event_id == Event.event_id)
        .filter(Event.event_type.in_(["danger", "alert"]))   # pass 제외
    )

    if session_id:
        q = q.filter(EventFeedback.client_session_uuid == session_id)

    # Event에 ts_ms 컬럼이 있다면 거기 사용. (너는 segment_start_ms 쓰고 있지?)
    if since_ts_ms is not None:
        q = q.filter(Event.segment_start_ms >= since_ts_ms)
    if until_ts_ms is not None:
        q = q.filter(Event.segment_start_ms <= until_ts_ms)

    q = q.group_by(Event.event_type, Event.keyword)

    rows = q.all()

    # down_rate 계산 + 정렬
    out = []
    for r in rows:
        total = int(r.total or 0)
        down = int(r.down_cnt or 0)
        up = int(r.up_cnt or 0)
        down_rate = (down / total) if total > 0 else 0.0
        out.append({
            "event_type": r.event_type,
            "keyword": r.keyword or "",
            "total": total,
            "up": up,
            "down": down,
            "down_rate": round(down_rate, 3),
        })

    out.sort(key=lambda x: (x["down_rate"], x["total"]), reverse=True)
    return out[:limit]


def feedback_suspects(
    db: Session,
    session_id: Optional[str] = None,
    since_ts_ms: Optional[int] = None,
    until_ts_ms: Optional[int] = None,
    min_count: int = 5,
    min_down_rate: float = 0.6,
    limit: int = 20,
):
    """
    오탐 의심(Down 비율 높은) 키워드/라벨 후보 자동 추천
    """
    items = feedback_summary(
        db=db,
        session_id=session_id,
        since_ts_ms=since_ts_ms,
        until_ts_ms=until_ts_ms,
        limit=500,
    )

    suspects = [
        x for x in items
        if x["total"] >= min_count and x["down_rate"] >= min_down_rate
    ]
    return suspects[:limit]