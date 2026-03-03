"""
WebSocket 메시지 처리: join, caption(브로드캐스트 + 로그 + 키워드 알림).
메모리 브로드캐스트 + DB 저장.
"""
import asyncio

from fastapi import WebSocket

from App.Services import keyword_detector
from App.WS.manager import manager
from App.Services.memory_logs import memory_logs


def _persist_caption(client_session_uuid: str, text: str, ts_ms: int) -> None:
    from App.db.crud import events as crud_events
    from App.db.database import SessionLocal

    db = SessionLocal()
    try:
        crud_events.create_caption_event(db, client_session_uuid, text, ts_ms)
    finally:
        db.close()


def _persist_alert(
    client_session_uuid: str, text: str, keyword: str, event_type: str, ts_ms: int
) -> None:
    from App.db.crud import events as crud_events
    from App.db.database import SessionLocal

    db = SessionLocal()
    try:
        crud_events.create_alert_event(db, client_session_uuid, text, keyword, event_type, ts_ms)
    finally:
        db.close()


async def handle_message(
    websocket: WebSocket,
    msg: dict,
    session_id: str | None,
) -> str | None:
    msg_type = msg.get("type")

    if msg_type == "join":
        sid = msg.get("session_id")
        if sid:
            await manager.connect(websocket, sid)
            await websocket.send_json({"type": "join_ack", "session_id": sid})
            return sid
        return session_id

    if msg_type == "caption":
        sid = msg.get("session_id")
        text = msg.get("text", "")
        if not sid:
            return session_id
        new_sid = session_id if session_id else sid
        if session_id is None:
            await manager.connect(websocket, sid)

        caption_entry = memory_logs.append_caption(sid, text)
        await manager.broadcast_to_session(sid, caption_entry, exclude=websocket)
        await asyncio.to_thread(_persist_caption, sid, text, caption_entry["ts_ms"])

        for kw, etype in keyword_detector.check_alerts(text):
            entry = memory_logs.append_alert(sid, text, kw, etype)
            await manager.broadcast_to_session(sid, entry)
            await asyncio.to_thread(_persist_alert, sid, text, kw, etype, entry["ts_ms"])

        return new_sid

    if session_id is None and msg.get("session_id"):
        return msg["session_id"]

    return session_id
