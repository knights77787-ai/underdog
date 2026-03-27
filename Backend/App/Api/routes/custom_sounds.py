# App/Api/routes/custom_sounds.py
import os
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
from fastapi import APIRouter, Depends, File, Form, HTTPException, Path as ApiPath, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from App.Core.config import CUSTOM_SOUND_AUDIO_RETENTION_HOURS, DATABASE_PATH
from App.Services.audio_io import decode_audio_to_16k_mono_f32
from App.db.crud.custom_sounds import (
    create_custom_sound,
    delete_custom_sound,
    expire_stale_custom_sounds_audio_for_session,
    list_custom_sounds,
    maybe_expire_custom_sound_audio,
    resolve_custom_sound_disk_path,
)
from App.db.crud.sessions import get_or_create_by_client_uuid
from App.db.database import get_db
from App.db.models import Session as SessionModel
from App.Services.yamnet_service import YamnetService

router = APIRouter(prefix="/custom-sounds", tags=["custom-sounds"])
_upload_debug_last_ts: int = 0

# Backend/data/custom_sounds에 저장 (절대 경로로 CWD 의존 제거)
_UPLOAD_BASE = Path(DATABASE_PATH).resolve().parent / "custom_sounds"
UPLOAD_DIR = _UPLOAD_BASE
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

_yamnet_instance: YamnetService | None = None
_yamnet_error: str | None = None


def _resolve_user_id_from_session(db: Session, session_id: str) -> int | None:
    row = (
        db.query(SessionModel)
        .filter(SessionModel.client_session_uuid == session_id)
        .first()
    )
    return int(row.user_id) if row and row.user_id is not None else None


def _get_yamnet() -> YamnetService:
    """YAMNET 모델 지연 로드. 첫 사용 시에만 로드하며, 실패 시 503 안내."""
    global _yamnet_instance, _yamnet_error
    if _yamnet_instance is not None:
        return _yamnet_instance
    if _yamnet_error is not None:
        raise HTTPException(
            503,
            f"YAMNET 모델 로드 실패(캐시 손상 가능). "
            f"TF Hub 캐시 삭제 후 재시도: 사용자 임시 폴더(AppData\\Local\\Temp) 안의 tfhub_modules 폴더 삭제. 원인: {_yamnet_error}",
        )
    try:
        _yamnet_instance = YamnetService()
        return _yamnet_instance
    except Exception as e:
        _yamnet_error = str(e)
        raise HTTPException(
            503,
            f"YAMNET 모델 로드 실패. "
            f"캐시 삭제 후 재시도: 사용자 임시 폴더(AppData\\Local\\Temp) 안의 tfhub_modules 폴더 삭제. 원인: {_yamnet_error}",
        )

ALLOWED_EXTENSIONS = (".wav", ".mp3", ".weba", ".m4a", ".ogg")


def _custom_sound_quality_report(x16k: np.ndarray) -> dict:
    """등록 음원 품질 지표(간단): 길이, RMS, clipping 비율, 권고 메시지."""
    n = int(x16k.shape[0])
    secs = float(n / 16000.0) if n > 0 else 0.0
    rms = float(np.sqrt(np.mean(np.square(x16k))) + 1e-12) if n > 0 else 0.0
    clip_ratio = float(np.mean(np.abs(x16k) >= 0.98)) if n > 0 else 0.0
    warnings: list[str] = []
    if secs < 1.0:
        warnings.append("소리 길이가 매우 짧습니다(1초 미만).")
    elif secs < 2.0:
        warnings.append("소리 길이가 짧습니다(2초 미만).")
    if rms < 0.01:
        warnings.append("입력 음압이 낮습니다. 소리를 더 가깝고 크게 녹음해 주세요.")
    if clip_ratio > 0.05:
        warnings.append("클리핑(찢어짐) 비율이 높습니다. 입력 볼륨을 조금 낮춰 녹음해 주세요.")
    return {
        "duration_sec": round(secs, 3),
        "rms": round(rms, 6),
        "clip_ratio": round(clip_ratio, 6),
        "warnings": warnings,
    }

def _normalize_1s_window(x: np.ndarray) -> np.ndarray:
    """호환용: 마지막 1초(또는 짧으면 0 패딩) 16000 samples 윈도우 생성."""
    if x.shape[0] < 16000:
        return (
            np.pad(x, (0, 16000 - x.shape[0]), mode="constant", constant_values=0.0)
            .astype(np.float32)
        )
    return x[-16000:].astype(np.float32)


def _window_1s_from_start(x: np.ndarray) -> np.ndarray:
    """시작 1초(또는 짧으면 0 패딩) 16000 samples 윈도우 생성."""
    if x.shape[0] < 16000:
        return (
            np.pad(x, (0, 16000 - x.shape[0]), mode="constant", constant_values=0.0)
            .astype(np.float32)
        )
    return x[:16000].astype(np.float32)

@router.post("")
async def upload_custom_sound(
    session_id: str = Query(..., description="클라이언트 세션 문자열 예: S1"),
    name: str = Form(...),
    event_type: str = Form(..., description="danger | caution | alert"),
    match_threshold: float | None = Form(
        None, description="0~1. 개별 커스텀 임계값(비우면 전역 설정 사용)"
    ),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    fn = (file.filename or "").lower()
    ext = next((e for e in ALLOWED_EXTENSIONS if fn.endswith(e)), None)
    if not ext:
        raise HTTPException(400, f"지원 형식: {', '.join(ALLOWED_EXTENSIONS)}")

    raw_bytes = await file.read()
    x16k = decode_audio_to_16k_mono_f32(raw_bytes, ext, allowed_extensions=ALLOWED_EXTENSIONS)

    yamnet = _get_yamnet()
    # 업로드 임베딩을 "시작/가운데/끝" 여러 1초 조각으로 만들고 평균 내서
    # 녹음 타이밍(짖는 구간이 앞/뒤에 안 들어가는 경우)에 덜 민감하게 합니다.
    x_start = _window_1s_from_start(x16k)
    x_end = _normalize_1s_window(x16k)  # last 1s

    if x16k.shape[0] >= 16000:
        mid = int(x16k.shape[0] // 2)
        s = max(0, mid - 8000)
        e = s + 16000
        x_mid = x16k[s:e]
        if x_mid.shape[0] < 16000:
            x_mid = np.pad(
                x_mid, (0, 16000 - x_mid.shape[0]), mode="constant", constant_values=0.0
            ).astype(np.float32)
        else:
            x_mid = x_mid.astype(np.float32)
    else:
        x_mid = x16k
    if x_mid.shape[0] != 16000:
        x_mid = _normalize_1s_window(x_mid)

    emb_start = yamnet.embedding_1s(x_start)
    emb_mid = yamnet.embedding_1s(x_mid)
    emb_end = yamnet.embedding_1s(x_end)
    emb = (emb_start + emb_mid + emb_end) / 3.0

    # 평균 후에도 코사인 유사도 계산용으로 정규화(단위 벡터)
    n = np.linalg.norm(emb) + 1e-9
    emb = (emb / n).astype(np.float32)

    # 파일 저장 (원본 확장자 유지). DB에는 "data/custom_sounds/..." 형태로 저장
    save_path = UPLOAD_DIR / f"{session_id}_{file.filename}"
    save_path.write_bytes(raw_bytes)
    audio_path_for_db = f"data/custom_sounds/{session_id}_{file.filename}"

    session_row = get_or_create_by_client_uuid(db, session_id)
    user_id = session_row.user_id if session_row else None

    if match_threshold is not None:
        try:
            match_threshold = float(match_threshold)
        except (TypeError, ValueError):
            raise HTTPException(400, "match_threshold는 숫자여야 합니다.")
        if not (0.0 < match_threshold <= 1.0):
            raise HTTPException(400, "match_threshold는 0~1 범위여야 합니다.")
    else:
        # 기본은 운영 .env 기준(없으면 코드 기본값 0.75)
        mt = (os.getenv("CUSTOM_SOUND_THRESHOLD") or "").strip()
        match_threshold = float(mt) if mt else 0.75

    quality = _custom_sound_quality_report(x16k)

    row = create_custom_sound(
        db=db,
        client_session_uuid=session_id,
        name=name,
        event_type=event_type,
        emb=emb,
        audio_path=audio_path_for_db,
        user_id=user_id,
        match_threshold=match_threshold,
    )

    # 업로드 직후 세션/ID를 로그로 남겨, 실시간 매칭 워커의 sid와 매칭되는지 확인합니다.
    # 너무 자주 찍히지 않도록 1초 throttle.
    global _upload_debug_last_ts
    now_ts = int(datetime.utcnow().timestamp() * 1000)
    if now_ts - _upload_debug_last_ts > 1000:
        print(
            f"[custom_sounds.upload] session_id={session_id} custom_sound_id={row.custom_sound_id} event_type={event_type} name={name}",
            flush=True,
        )
        _upload_debug_last_ts = now_ts

    return {
        "ok": True,
        "data": {
            "custom_sound_id": row.custom_sound_id,
            "name": row.name,
            "match_threshold": row.match_threshold,
            "quality": quality,
            "audio_retention_hours": CUSTOM_SOUND_AUDIO_RETENTION_HOURS,
        },
    }

@router.get("/{custom_sound_id}/audio")
def get_custom_sound_audio(
    custom_sound_id: int = ApiPath(...),
    session_id: str = Query(...),
    db: Session = Depends(get_db),
):
    """커스텀 소리 오디오 파일 스트리밍 (재생용). 보관 기간 만료 시 410."""
    user_id = _resolve_user_id_from_session(db, session_id)
    rows = list_custom_sounds(db, session_id, user_id=user_id)
    row = next((r for r in rows if r.custom_sound_id == custom_sound_id), None)
    if not row:
        raise HTTPException(404, "해당 소리를 찾을 수 없거나 권한이 없습니다.")
    maybe_expire_custom_sound_audio(db, row)
    fp = resolve_custom_sound_disk_path(row.audio_path)
    if not fp:
        deadline = row.created_at + timedelta(hours=CUSTOM_SOUND_AUDIO_RETENTION_HOURS)
        if not row.audio_path or datetime.utcnow() > deadline:
            raise HTTPException(
                410,
                "원본 음원 보관 기간이 만료되어 재생할 수 없습니다. 실시간 감지(임베딩)는 계속 이용할 수 있습니다.",
            )
        raise HTTPException(404, "오디오 파일을 찾을 수 없습니다.")
    ext = fp.suffix.lower()
    media_map = {
        ".mp3": "audio/mpeg",
        ".wav": "audio/wav",
        ".weba": "audio/webm",
        ".webm": "audio/webm",  # 과거 업로드 분만 재생 호환
        ".m4a": "audio/mp4",
        ".ogg": "audio/ogg",
    }
    media_type = media_map.get(ext, "application/octet-stream")
    return FileResponse(fp, media_type=media_type)


@router.get("")
def get_custom_sounds(
    session_id: str = Query(...),
    db: Session = Depends(get_db),
):
    user_id = _resolve_user_id_from_session(db, session_id)
    # 로그인 사용자는 해당 계정의 전체 등록음을 보여주므로 만료 정리는 user_id 범위로 수행
    if user_id is not None:
        rows_for_expire = list_custom_sounds(db, session_id, user_id=user_id)
        for r in rows_for_expire:
            maybe_expire_custom_sound_audio(db, r)
    else:
        expire_stale_custom_sounds_audio_for_session(db, session_id)
    rows = list_custom_sounds(db, session_id, user_id=user_id)
    now = datetime.utcnow()
    out = []
    for r in rows:
        deadline = r.created_at + timedelta(hours=CUSTOM_SOUND_AUDIO_RETENTION_HOURS)
        audio_available = bool(r.audio_path) and now <= deadline
        out.append(
            {
                "custom_sound_id": r.custom_sound_id,
                "name": r.name,
                "event_type": r.event_type,
                "match_threshold": r.match_threshold,
                "audio_path": r.audio_path,
                "created_at": r.created_at,
                "audio_available": audio_available,
                "audio_expires_at": deadline.isoformat() + "Z",
            }
        )
    return {
        "ok": True,
        "count": len(out),
        "audio_retention_hours": CUSTOM_SOUND_AUDIO_RETENTION_HOURS,
        "data": out,
    }


@router.delete("/{custom_sound_id}")
def remove_custom_sound(
    custom_sound_id: int = ApiPath(..., description="삭제할 커스텀 사운드 ID"),
    session_id: str = Query(..., description="클라이언트 세션 문자열 예: S1"),
    db: Session = Depends(get_db),
):
    """
    커스텀 사운드 1건 삭제.
    - 세션 ID를 함께 받아 해당 세션이 소유한 항목만 삭제.
    - DB 레코드와 연결된 오디오 파일을 함께 제거.
    """
    user_id = _resolve_user_id_from_session(db, session_id)
    deleted = delete_custom_sound(
        db,
        client_session_uuid=session_id,
        custom_sound_id=custom_sound_id,
        user_id=user_id,
    )
    if not deleted:
        raise HTTPException(404, "해당 소리를 찾을 수 없거나 권한이 없습니다.")
    return {"ok": True}