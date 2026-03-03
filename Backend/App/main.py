"""
underdog AI Pipeline - FastAPI 앱 (App 폴더 진입점)
DB: SQLite 연동, 기동 시 테이블 생성.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from App.Api.routes.admin import router as admin_router
from App.Api.routes.feedback import router as feedback_router
from App.Api.routes.health import router as health_router
from App.Api.routes.logs import router as logs_router
from App.Api.routes.settings import router as settings_router
from App.WS.endpoint import router as ws_router
from App.db.database import create_tables


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    yield


app = FastAPI(title="Underdog AI Backend", version="0.1.0", lifespan=lifespan)

# REST 라우트 등록
app.include_router(health_router)
app.include_router(logs_router)
app.include_router(admin_router)
app.include_router(feedback_router)
app.include_router(settings_router)

# WebSocket 라우트 등록
app.include_router(ws_router)
