"""
WebSocket 메시지 처리: join, caption(브로드캐스트 + 로그 + 키워드 알림).
"""
from fastapi import WebSocket

from App.Services import keyword_detector
from App.WS.manager import manager
from App.Services.memory_logs import memory_logs


async def handle_message(
    websocket: WebSocket,
    msg: dict,
    session_id: str | None,
) -> str | None:
    """
    메시지 처리. session_id 갱신 시 새 값 반환, join/caption에서 세션 등록.
    """
    msg_type = msg.get("type")

    if msg_type == "join":
        sid = msg.get("session_id")
        if sid:
            await manager.connect(websocket, sid)
            # 선택: join_ack 지원 (디버깅 편의)
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

        # 서버 표준 형태(ts_ms)로 저장 후 같은 엔트리로 브로드캐스트 (시간 필드 통일)
        caption_entry = memory_logs.append_caption(sid, text)
        await manager.broadcast_to_session(sid, caption_entry, exclude=websocket)

        for kw, etype in keyword_detector.check_alerts(text):
            entry = memory_logs.append_alert(sid, text, kw, etype)
            await manager.broadcast_to_session(sid, entry)

        return new_sid

    if session_id is None and msg.get("session_id"):
        return msg["session_id"]

    return session_id