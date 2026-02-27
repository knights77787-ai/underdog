"""WebSocket /ws 엔드포인트."""
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from App.WS import handlers

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """/ws 진입점.

    - 연결 시 서버가 hello 전송
    - 클라이언트가 hello 보내면 여기서 hello_ack 응답
    - 나머지(join, caption 등)는 모두 handlers.handle_message 로 위임
    """
    await websocket.accept()
    session_id: str | None = None
    await websocket.send_json({"type": "hello"})

    try:
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
            except json.JSONDecodeError:
                continue

            msg_type = msg.get("type")
            if msg_type == "hello":
                await websocket.send_json({"type": "hello_ack"})
                continue

            # join, caption, 기타 메시지는 모두 handlers 로 위임
            session_id = await handlers.handle_message(websocket, msg, session_id)
    except WebSocketDisconnect:
        pass
    finally:
        # 마지막에 등록된 세션에서 연결 정리
        if session_id:
            from App.WS.manager import manager

            manager.disconnect(websocket, session_id)
