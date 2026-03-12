"""
underdog AI Pipeline - FastAPI 앱 (App 폴더 진입점)
DB: SQLite 연동, 기동 시 테이블 생성.
프론트엔드: /, /login, /live → HTML, /static → 정적 파일 (Frontend 폴더 기준).
"""
import asyncio
import os
import uuid
from pathlib import Path
from contextlib import asynccontextmanager

from dotenv import load_dotenv

# .env 로드 (config import 전에 반드시 실행 → ADMIN_TOKEN 등 로드)
_backend_dir = Path(__file__).resolve().parent.parent  # .../Backend
_repo_root_dir = _backend_dir.parent  # .../underdog (repo root)
for _env_path in (_backend_dir / ".env", _repo_root_dir / ".env"):
    if _env_path.is_file():
        load_dotenv(_env_path)
        break
else:
    load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from App.Api.routes.admin import router as admin_router
from App.Api.routes.auth import router as auth_router
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

from fastapi import Body
from App.WS.manager import manager
from App.WS.handlers import memory_logs, keyword_detector  # 이미 있으면 생략
import time


@asynccontextmanager
async def lifespan(app: FastAPI):
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    setup_logging(log_level)  # 서버가 무슨일을 했는지 콘솔/파일에 기록 남기는것
    create_tables()     # 서버 켤 때 한번 '없으면 생성' 을 해두는 안전장치.
    get_logger("app").info(
        "app_started level=%s db=%s", log_level, DATABASE_PATH
    )   # 서버가 정상 기동됐는지 확인하는 최초신호

    # 오디오 분류(Yamnet) worker: 비언어 1초 윈도우 → AUDIOCLS_QUEUE → 분류/alert
    # 검증: 1) 서버 기동 시 yamnet_worker_started 로그 2) 비언어 상태에서 환경음 재생
    #       3) 콘솔에 YAMNET top=... score=... mapped=... 4) 매핑되면 /admin/alerts 에 source:"audio" 적재
    reload_audio_rules()  

    async def _broadcast_yamnet(sid: str, entry: dict) -> None:
        await manager.broadcast_to_session(sid, entry)

    def _persist_alert_and_record_ts(
        sid, text, keyword, event_type, ts_ms,
        *, matched_custom_sound_id=None, custom_similarity=None,
    ):
        """DB 저장 + 쿨다운 기록. event_id 반환 (커스텀 사운드 등 WS 브로드캐스트용)."""
        event_id = handlers._persist_alert(
            sid, text, keyword, event_type, ts_ms,
            matched_custom_sound_id=matched_custom_sound_id,
            custom_similarity=custom_similarity,
        )
        handlers.record_alert_ts(sid, keyword, event_type, ts_ms)
        return event_id

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

    # STT 큐 워커: VAD_END → STT_QUEUE → 3개 워커가 Whisper 병렬 처리 (반응 지연 완화)
    app.state.stt_worker = SttWorker(handlers.STT_QUEUE)
    app.state.stt_task = asyncio.create_task(app.state.stt_worker.run())
    app.state.stt_worker_2 = SttWorker(handlers.STT_QUEUE)
    app.state.stt_task_2 = asyncio.create_task(app.state.stt_worker_2.run())
    app.state.stt_worker_3 = SttWorker(handlers.STT_QUEUE)
    app.state.stt_task_3 = asyncio.create_task(app.state.stt_worker_3.run())

    yield

    # shutdown: worker tasks 취소
    for name in ("yamnet_task", "stt_task", "stt_task_2", "stt_task_3"):
        t = getattr(app.state, name, None)
        if t is not None:
            t.cancel()
            try:
                await t
            except asyncio.CancelledError:
                pass


app = FastAPI(title="Underdog AI Backend", version="0.1.0", lifespan=lifespan)
app_logger = get_logger("app")

# CORS: 프론트(웹/RN)에서 API 호출 시 차단 방지. 개발 중엔 * OK (배포 시 도메인 제한)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
app.include_router(auth_router)



# WebSocket 라우트 등록
app.include_router(ws_router)

# 커스텀 사운드 / 커스텀 구문 업로드·조회
app.include_router(custom_sounds_router)
app.include_router(custom_phrase_audio_router)

# ---------- 프론트엔드 서빙 (API 라우트보다 나중에 등록) ----------
# 프로젝트 루트 = Backend의 상위(underdog). Frontend = 루트/Frontend
_FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "Frontend"
_FRONTEND_STATIC = _FRONTEND_DIR / "static"
_FRONTEND_TEMPLATES = _FRONTEND_DIR / "templates"


def _send_html(name: str):
    path = _FRONTEND_TEMPLATES / name
    if not path.is_file():
        return FileResponse(_FRONTEND_TEMPLATES / "index.html")
    return FileResponse(path, media_type="text/html; charset=utf-8")


@app.get("/", response_class=FileResponse)
def frontend_index():
    """라이브 메인 페이지."""
    return _send_html("index.html")


@app.get("/login", response_class=FileResponse)
def frontend_login():
    """로그인 페이지."""
    return _send_html("login.html")


@app.get("/live", response_class=FileResponse)
def frontend_live():
    """라이브 페이지 (구글/카카오 콜백 리다이렉트용). index와 동일."""
    return _send_html("index.html")


@app.get("/new-sound", response_class=FileResponse)
def frontend_new_sound():
    """커스텀 소리 등록·목록 페이지."""
    return _send_html("new_sound.html")


@app.get("/admin-login", response_class=FileResponse)
def frontend_admin_login():
    """관리자 로그인 페이지."""
    return _send_html("ad_login.html")


@app.get("/admin", response_class=FileResponse)
def frontend_admin():
    """관리자 대시보드 페이지. 로그인 필요."""
    return _send_html("admin.html")


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    """기본 /favicon.ico 요청을 static/favicon.svg 로 리다이렉트."""
    return RedirectResponse(url="/static/favicon.svg", status_code=302)


if _FRONTEND_STATIC.is_dir():
    app.mount("/static", StaticFiles(directory=str(_FRONTEND_STATIC)), name="static")

# 커스텀 소리 오디오 파일 서빙 (재생용). Backend/data → /data
_DATA_DIR = _backend_dir / "data"
if _DATA_DIR.is_dir():
    app.mount("/data", StaticFiles(directory=str(_DATA_DIR)), name="data")