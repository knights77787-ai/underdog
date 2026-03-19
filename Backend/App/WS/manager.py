"""세션별 WebSocket 연결 관리 (브로드캐스트)."""
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self.sessions: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, session_id: str) -> None:
        if session_id not in self.sessions:
            self.sessions[session_id] = []
        # 같은 소켓이 중복 등록되면 브로드캐스트가 중복될 수 있어 1회만 유지
        if websocket not in self.sessions[session_id]:
            self.sessions[session_id].append(websocket)

    def disconnect(self, websocket: WebSocket, session_id: str) -> None:
        if session_id in self.sessions:
            try:
                self.sessions[session_id].remove(websocket)
            except ValueError:
                pass
            if not self.sessions[session_id]:
                del self.sessions[session_id]

    async def broadcast_to_session(
        self,
        session_id: str,
        message: dict,
        exclude: WebSocket | None = None,
    ) -> None:
        if session_id not in self.sessions:
            return
        dead = []
        for ws in self.sessions[session_id]:
            if ws is exclude:
                continue
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws, session_id)


manager = ConnectionManager()
