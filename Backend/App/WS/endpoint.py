"""WebSocket /ws 엔드포인트.

안정화: ping/pong, 잘못된 메시지(JSON 깨짐/비객체) 시 서버 유지, disconnect 시 세션에서 제거.
관측 디버깅: 연결마다 conn_id 부여, 모든 로그에 [conn=conn_id] 넣어 한 연결 추적 가능.
(extra는 기본 포맷에 안 나오므로 메시지 문자열에 직접 포함)
"""
import json
import time
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from App.Core.logging import get_logger
from App.WS import handlers

router = APIRouter()
logger = get_logger("ws.endpoint")


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
    conn_id = uuid.uuid4().hex[:8]
    logger.info(f"[conn={conn_id}] ws_connected client={websocket.client}")
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
                # 연결 직후엔 session_id가 None인 것이 정상(join 전). join 후 hello 재전송은 프론트에서 지양.
                await websocket.send_json({"type": "hello_ack", "session_id": session_id})
                continue
            if msg_type == "ping":
                logger.debug(f"[conn={conn_id}] ws_ping session_id={session_id}")
                await websocket.send_json({"type": "pong", "ts_ms": int(time.time() * 1000)})
                continue

            # join, caption, 기타 메시지는 handlers 로 위임 (예외 시에도 서버 유지)
            try:
                session_id = await handlers.handle_message(
                    websocket, msg, session_id, conn_id=conn_id
                )
            except Exception:
                logger.exception(
                    f"[conn={conn_id}] ws_handler_error session_id={session_id} msg_type={msg.get('type')}"
                )
                await websocket.send_json({"type": "error", "message": "handler_failed"})
                continue
    except WebSocketDisconnect:
        pass
    finally:
        logger.info(f"[conn={conn_id}] ws_disconnected session_id={session_id} client={websocket.client}")
        if session_id:
            from App.WS.manager import manager

            handlers.clear_cooldown_for_session(session_id)
            handlers.AUDIO_STATES.remove(session_id)
            manager.disconnect(websocket, session_id)
