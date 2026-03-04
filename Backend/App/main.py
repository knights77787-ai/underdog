"""
underdog AI Pipeline - FastAPI 앱 (App 폴더 진입점)
DB: SQLite 연동, 기동 시 테이블 생성.
"""
import asyncio
import os
import uuid
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI

from App.Api.routes.admin import router as admin_router
from App.Api.routes.feedback import router as feedback_router
from App.Api.routes.health import router as health_router
from App.Api.routes.custom_phrase_audio import router as custom_phrase_audio_router
from App.Api.routes.custom_sounds import router as custom_sounds_router
from App.Api.routes.logs import router as logs_router
from App.Api.routes.settings import router as settings_router
from App.Core.config import DATABASE_PATH
from App.Core.logging import get_logger, setup_logging
from App.Services.audio_rules import reload_audio_rules
from App.WS.audio_cls_worker import AudioClsWorker
from App.WS.endpoint import router as ws_router
from App.WS import handlers
from App.WS.manager import manager
from App.WS.stt_worker import SttWorker
from App.db.database import create_tables

load_dotenv()  # .env 에서 ADMIN_TOKEN 등 로드


@asynccontextmanager
async def lifespan(app: FastAPI):
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    setup_logging(log_level)
    create_tables()
    get_logger("app").info(
        "app_started level=%s db=%s", log_level, DATABASE_PATH
    )

    # 오디오 분류(Yamnet) worker: 비말 1초 윈도우 → AUDIOCLS_QUEUE → 분류/alert
    # 검증: 1) 서버 기동 시 yamnet_worker_started 로그 2) 비말 상태에서 환경음 재생
    #       3) 콘솔에 YAMNET top=... score=... mapped=... 4) 매핑되면 /admin/alerts 에 source:"audio" 적재
    reload_audio_rules()
    async def _broadcast_yamnet(sid: str, entry: dict) -> None:
        await manager.broadcast_to_session(sid, entry)

    def _persist_alert_and_record_ts(sid, text, keyword, event_type, ts_ms):
        # keyword는 worker가 이미 "yamnet:..." 형태로 넘김 (prefix 한 군데만)
        handlers._persist_alert(sid, text, keyword, event_type, ts_ms)
        handlers.record_alert_ts(sid, keyword, event_type, ts_ms)

    app.state.yamnet_worker = AudioClsWorker(
        handlers.AUDIOCLS_QUEUE,
        _broadcast_yamnet,
        _persist_alert_and_record_ts,
        lambda sid, kw, et, cooldown_sec, ts_ms: handlers._is_in_cooldown(
            sid, kw, et, cooldown_sec, ts_ms
        ),
    )
    app.state.yamnet_task = asyncio.create_task(
        app.state.yamnet_worker.run()
    )

    # STT 큐 워커: VAD_END → STT_QUEUE → 단일 워커가 Whisper 직렬 처리
    app.state.stt_worker = SttWorker(handlers.STT_QUEUE)
    app.state.stt_task = asyncio.create_task(app.state.stt_worker.run())

    yield

    # shutdown: worker tasks 취소
    for name in ("yamnet_task", "stt_task"):
        t = getattr(app.state, name, None)
        if t is not None:
            t.cancel()
            try:
                await t
            except asyncio.CancelledError:
                pass


app = FastAPI(title="Underdog AI Backend", version="0.1.0", lifespan=lifespan)
app_logger = get_logger("app")


@app.middleware("http")
async def log_requests(request, call_next):
    """REST 요청/응답 요약 로그. request_id로 한 요청 흐름 추적(로그 상관관계)."""
    request_id = uuid.uuid4().hex[:8]
    request.state.request_id = request_id
    response = await call_next(request)
    app_logger.info(
        "[req=%s] rest %s %s %s",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
    )
    return response


# REST 라우트 등록
app.include_router(health_router)
app.include_router(logs_router)
app.include_router(admin_router)
app.include_router(feedback_router)
app.include_router(settings_router)

# WebSocket 라우트 등록
app.include_router(ws_router)

# 커스텀 사운드 / 커스텀 구문 업로드·조회
app.include_router(custom_sounds_router)
app.include_router(custom_phrase_audio_router)