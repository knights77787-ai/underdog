"""WebSocket /ws 엔드포인트.

안정화: ping/pong, 잘못된 메시지(JSON 깨짐/비객체) 시 서버 유지, disconnect 시 세션에서 제거.
"""
import json
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from App.WS import handlers

router = APIRouter()


def _parse_message(text: str) -> dict | None:
    """JSON 파싱. 깨진 JSON 또는 객체가 아니면 None."""
    try:
        msg = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(msg, dict):
        return None
    return msg


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """/ws 진입점.

    - 연결 시 서버가 hello 전송
    - 클라이언트 hello → hello_ack, ping → pong (ts_ms 포함)
    - join, caption 등은 handlers.handle_message 로 위임
    - 잘못된 메시지(JSON 깨짐/비객체)는 무시하고 루프 유지
    - disconnect 시 세션에서 해당 ws 제거(이미 구현됨)
    """
    await websocket.accept()
    session_id: str | None = None
    await websocket.send_json({"type": "hello"})

    try:
        while True:
            data = await websocket.receive_text()
            msg = _parse_message(data)
            if msg is None:
                continue

            msg_type = msg.get("type")
            if msg_type == "hello":
                await websocket.send_json({"type": "hello_ack"})
                continue
            if msg_type == "ping":
                await websocket.send_json({"type": "pong", "ts_ms": int(time.time() * 1000)})
                continue

            # join, caption, 기타 메시지는 handlers 로 위임 (예외 시에도 서버 유지)
            try:
                session_id = await handlers.handle_message(websocket, msg, session_id)
            except Exception:
                await websocket.send_json({"type": "error", "message": "handler_failed"})
                continue
    except WebSocketDisconnect:
        pass
    finally:
        # disconnect 시 세션에서 해당 ws 제거. join 된 것만 세션에 있으므로 session_id 있을 때만 호출
        if session_id:
            from App.WS.manager import manager

            manager.disconnect(websocket, session_id)
