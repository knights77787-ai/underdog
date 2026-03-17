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

# TensorFlow C++ 로그 억제 (INFO 메시지 안 보이게)
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")  # 0=all 1=INFO 2=WARN 3=ERROR only

# 로깅 먼저 설정 (handlers/STT 로드 시 진행상황 출력)
from App.Core.logging import setup_logging
setup_logging(os.environ.get("LOG_LEVEL", "INFO").upper())

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
from App.Core.logging import get_logger
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


def _is_heavy_workers_enabled() -> bool:
    """Render 등 메모리 제한 환경에서는 0 또는 비설정 시 워커 비활성화 → 가벼운 기동."""
    v = os.environ.get("ENABLE_ML_WORKERS", "").strip().lower()
    return v in ("1", "true", "yes")


def _is_yamnet_enabled() -> bool:
    """YAMNet(비언어 오디오 분류) 워커 활성 여부. 기본 ON, Render 등에서는 ENABLE_YAMNET=0 으로 비활성화 가능."""
    v = os.environ.get("ENABLE_YAMNET", "1").strip().lower()
    return v in ("1", "true", "yes")


@asynccontextmanager
async def lifespan(app: FastAPI):
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    create_tables()     # 서버 켤 때 한번 '없으면 생성' 을 해두는 안전장치.
    get_logger("app").info(
        "app_started level=%s db=%s", log_level, DATABASE_PATH
    )   # 서버가 정상 기동됐는지 확인하는 최초신호

    # 무거운 기동(Yamnet/STT 워커, rules reload)은 ENABLE_ML_WORKERS=1 일 때만 수행.
    # Render 등에서 OOM 방지: 기본값 비활성화 → /docs, /openapi.json 정상 응답 목표.
    if not _is_heavy_workers_enabled():
        get_logger("app").info("ENABLE_ML_WORKERS not set; skipping yamnet/stt workers and reload_audio_rules (light start)")
        app.state.yamnet_worker = None
        app.state.yamnet_task = None
        app.state.stt_worker = None
        app.state.stt_task = None
        app.state.stt_worker_2 = None
        app.state.stt_task_2 = None
        app.state.stt_worker_3 = None
        app.state.stt_task_3 = None
        yield
        return

    # 오디오 분류(Yamnet) worker: 비언어 1초 윈도우 → AUDIOCLS_QUEUE → 분류/alert
<<<<<<< HEAD
    print("[시작] 오디오 룰 로드 중...", flush=True)
    reload_audio_rules()
    print("[시작] 오디오 룰 로드 완료. YAMNet 워커 생성 중...", flush=True)
=======
<<<<<<< HEAD
    print("[시작] 오디오 룰 로드 중...", flush=True)
    reload_audio_rules()
    print("[시작] 오디오 룰 로드 완료. YAMNet 워커 생성 중...", flush=True)
=======
    # 메모리 사용량이 커서 Render 등 제한된 환경에서는 ENABLE_YAMNET=0 으로 비활성화 가능.
    if _is_yamnet_enabled():
        reload_audio_rules()
>>>>>>> ym04
>>>>>>> develop

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

<<<<<<< HEAD
    # YAMNet 워커 2개로 처리 속도 향상 (큐 적체 완화)
    app.state.yamnet_worker = AudioClsWorker(
        handlers.AUDIOCLS_QUEUE,
        _broadcast_yamnet,
        _persist_alert_and_record_ts,
        lambda sid, kw, et, cooldown_sec, ts_ms: handlers._is_in_cooldown(
            sid, kw, et, cooldown_sec, ts_ms
        ),
    )
    app.state.yamnet_worker_2 = AudioClsWorker(
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
    app.state.yamnet_task_2 = asyncio.create_task(
        app.state.yamnet_worker_2.run()
    )
    print("[시작] YAMNet 워커 시작 완료. STT 워커 시작 중...", flush=True)
<<<<<<< HEAD
=======
=======
        # YAMNet 워커 2개로 처리 속도 향상 (큐 적체 완화)
        app.state.yamnet_worker = AudioClsWorker(
            handlers.AUDIOCLS_QUEUE,
            _broadcast_yamnet,
            _persist_alert_and_record_ts,
            lambda sid, kw, et, cooldown_sec, ts_ms: handlers._is_in_cooldown(
                sid, kw, et, cooldown_sec, ts_ms
            ),
        )
        app.state.yamnet_worker_2 = AudioClsWorker(
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
        app.state.yamnet_task_2 = asyncio.create_task(
            app.state.yamnet_worker_2.run()
        )
    else:
        get_logger("app").info("ENABLE_YAMNET not set; skipping yamnet workers (STT only)")
        app.state.yamnet_worker = None
        app.state.yamnet_worker_2 = None
        app.state.yamnet_task = None
        app.state.yamnet_task_2 = None
>>>>>>> ym04
>>>>>>> develop

    # STT 큐 워커: VAD_END → STT_QUEUE → 3개 워커가 Whisper 병렬 처리
    app.state.stt_worker = SttWorker(handlers.STT_QUEUE)
    app.state.stt_task = asyncio.create_task(app.state.stt_worker.run())
    app.state.stt_worker_2 = SttWorker(handlers.STT_QUEUE)
    app.state.stt_task_2 = asyncio.create_task(app.state.stt_worker_2.run())
    app.state.stt_worker_3 = SttWorker(handlers.STT_QUEUE)
    app.state.stt_task_3 = asyncio.create_task(app.state.stt_worker_3.run())
    print("[시작] STT 워커 시작 완료. 서버 준비됨.", flush=True)

    yield

    # shutdown: worker tasks 취소
    for name in ("yamnet_task", "yamnet_task_2", "stt_task", "stt_task_2", "stt_task_3"):
        t = getattr(app.state, name, None)
        if t is not None:
            t.cancel()
            try:
                await t
            except asyncio.CancelledError:
                pass


app = FastAPI(title="Underdog AI Backend", version="0.1.0", lifespan=lifespan)
app_logger = get_logger("app")

# CORS: 프론트(웹/RN)에서 API 호출 시 차단. lumen.ai.kr 등 허용 (현재 * 로 전부 허용)
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



# WebSocket 라우트 등록 (배포 시 프록시가 /ws 업그레이드 전달해야 함)
app.include_router(ws_router)

# 커스텀 사운드 / 커스텀 구문 업로드·조회
app.include_router(custom_sounds_router)
app.include_router(custom_phrase_audio_router)

# ---------- 프론트엔드 서빙 (API 라우트보다 나중에 등록) ----------
# 프로젝트 루트 = Backend의 상위(underdog). Frontend = 루트/Frontend (배포 시 _repo_root_dir 기준)
_FRONTEND_DIR = _repo_root_dir / "Frontend"
_FRONTEND_STATIC = _FRONTEND_DIR / "static"
_FRONTEND_TEMPLATES = _FRONTEND_DIR / "templates"


def _send_html(name: str):
    path = _FRONTEND_TEMPLATES / name
    if not path.is_file():
        path = _FRONTEND_TEMPLATES / "index.html"
    if not path.is_file():
        return RedirectResponse(url="/docs", status_code=302)
    return FileResponse(path, media_type="text/html; charset=utf-8")


@app.get("/", include_in_schema=False)
def root():
    """루트(/) 접속 시: index.html 있으면 서빙, 없으면 /docs 로 리다이렉트."""
    path = _FRONTEND_TEMPLATES / "index.html"
    if path.is_file():
        return FileResponse(path, media_type="text/html; charset=utf-8")
    return RedirectResponse(url="/docs", status_code=302)


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


@app.get("/settings-page", response_class=FileResponse)
def frontend_settings():
    """설정 페이지."""
    return _send_html("settings.html")


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


@app.get("/health", include_in_schema=False)
def health():
    """서버·STT 활성 여부 점검 (메인 서버 자막 미동작 시 확인용)."""
    ml = os.environ.get("ENABLE_ML_WORKERS", "").strip().lower() in ("1", "true", "yes")
    api_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    stt_enabled = ml and bool(api_key)
    return {"ok": True, "stt_enabled": stt_enabled}


if _FRONTEND_STATIC.is_dir():
    app.mount("/static", StaticFiles(directory=str(_FRONTEND_STATIC)), name="static")

# 커스텀 소리 오디오 파일 서빙 (재생용). Backend/data → /data
_DATA_DIR = _backend_dir / "data"
if _DATA_DIR.is_dir():
    app.mount("/data", StaticFiles(directory=str(_DATA_DIR)), name="data")