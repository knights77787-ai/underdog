"""
underdog AI Pipeline - FastAPI 앱 (App 폴더 진입점)
마일스톤 1~5: 헬스체크, WebSocket hello/ack, caption 브로드캐스트, 키워드 알림, 로그 조회.
분류: Api/routes, WS, Services, Core, db, Schemas 에 맞게 배치.
"""
from fastapi import FastAPI

from App.Api.routes.health import router as health_router
from App.Api.routes.logs import router as logs_router
from App.WS.endpoint import router as ws_router

app = FastAPI(title="Underdog AI Backend", version="0.1.0")

# REST 라우트 등록
app.include_router(health_router)
app.include_router(logs_router)

# WebSocket 라우트 등록
app.include_router(ws_router)

