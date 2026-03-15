# app/Api/routes/custom_sounds.py
import io
from pathlib import Path

import numpy as np
import tensorflow as tf
from fastapi import APIRouter, Depends, File, Form, HTTPException, Path as ApiPath, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.crud.custom_sounds import (
    create_custom_sound,
    list_custom_sounds,
    delete_custom_sound,
)
from app.db.database import get_db
from app.Services.yamnet_service import YamnetService

from scipy.signal import resample

router = APIRouter(prefix="/custom-sounds", tags=["custom-sounds"])

# Backend/data/custom_sounds에 저장 (절대 경로로 CWD 의존 제거)
from app.Core.config import DATABASE_PATH
_UPLOAD_BASE = Path(DATABASE_PATH).resolve().parent / "custom_sounds"
UPLOAD_DIR = _UPLOAD_BASE
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

_yamnet_instance: YamnetService | None = None
_yamnet_error: str | None = None


def _get_yamnet() -> YamnetService:
    """YAMNET 모델 지연 로드. 첫 사용 시에만 로드하며, 실패 시 503 안내."""
    global _yamnet_instance, _yamnet_error
    if _yamnet_instance is not None:
        return _yamnet_instance
    if _yamnet_error is not None:
        raise HTTPException(
            503,
            f"YAMNET 모델 로드 실패(캐시 손상 가능). "
            "TF Hub 캐시 삭제 후 재시도: 사용자 임시 폴더(AppData\\Local\\Temp) 안의 tfhub_modules 폴더 삭제. 원인: {_yamnet_error}",
        )
    try:
        _yamnet_instance = YamnetService()
        return _yamnet_instance
    except Exception as e:
        _yamnet_error = str(e)
        raise HTTPException(
            503,
            f"YAMNET 모델 로드 실패. "
            "캐시 삭제 후 재시도: 사용자 임시 폴더(AppData\\Local\\Temp) 안의 tfhub_modules 폴더 삭제. 원인: {_yamnet_error}",
        )

ALLOWED_EXTENSIONS = (".wav", ".mp3", ".webm", ".m4a")

def _resample_to_16k(x: np.ndarray, sr: int) -> np.ndarray:
    if sr == 16000:
        return x.astype(np.float32)

    if sr <= 0:
        raise ValueError("invalid sample rate")

    new_len = int(round(len(x) * 16000 / sr))
    if new_len <= 0:
        raise ValueError("invalid resample length")

    y = resample(x, new_len)
    return y.astype(np.float32)

def _normalize_1s_window(x: np.ndarray) -> np.ndarray:
    if x.shape[0] < 16000:
        return np.pad(x, (0, 16000 - x.shape[0]), mode="constant", constant_values=0.0)
    return x[:16000].astype(np.float32)

def _decode_wav_to_16k_mono_f32(wav_bytes: bytes) -> np.ndarray:
    audio, sr = tf.audio.decode_wav(wav_bytes)  # (samples, channels) float32 -1..1
    audio = tf.reduce_mean(audio, axis=1)
    sr = int(sr.numpy())
    x = audio.numpy().astype(np.float32)
    x = _resample_to_16k(x, sr)
    return _normalize_1s_window(x)

def _decode_via_pydub(data: bytes, fmt: str) -> np.ndarray:
    """pydub로 mp3/webm 등 디코딩 → 16k mono float32."""
    try:
        from pydub import AudioSegment
    except ImportError:
        raise HTTPException(
            503,
            "오디오 디코딩을 위해 pydub가 필요합니다. pip install pydub 및 ffmpeg 설치 후 이용하세요.",
        )
    try:
        seg = AudioSegment.from_file(io.BytesIO(data), format=fmt)
    except Exception as e:
        raise HTTPException(400, f"{fmt.upper()} 디코딩 실패. ffmpeg 설치 여부를 확인하세요: {e!s}")
    seg = seg.set_channels(1)
    sr = seg.frame_rate
    samples = np.array(seg.get_array_of_samples(), dtype=np.float32) / 32768.0
    samples = _resample_to_16k(samples, sr)
    return _normalize_1s_window(samples)


def _decode_mp3_to_16k_mono_f32(mp3_bytes: bytes) -> np.ndarray:
    return _decode_via_pydub(mp3_bytes, "mp3")


def _decode_webm_to_16k_mono_f32(webm_bytes: bytes) -> np.ndarray:
    return _decode_via_pydub(webm_bytes, "webm")


def _decode_m4a_to_16k_mono_f32(m4a_bytes: bytes) -> np.ndarray:
    return _decode_via_pydub(m4a_bytes, "m4a")


def _decode_audio_to_16k_mono_f32(data: bytes, ext: str) -> np.ndarray:
    ext = ext.lower()
    if ext == ".wav":
        return _decode_wav_to_16k_mono_f32(data)
    if ext == ".mp3":
        return _decode_mp3_to_16k_mono_f32(data)
    if ext == ".webm":
        return _decode_webm_to_16k_mono_f32(data)
    if ext == ".m4a":
        return _decode_m4a_to_16k_mono_f32(data)
    raise HTTPException(400, f"지원하지 않는 형식입니다. 사용 가능: {', '.join(ALLOWED_EXTENSIONS)}")

@router.post("")
async def upload_custom_sound(
    session_id: str = Query(..., description="클라이언트 세션 문자열 예: S1"),
    name: str = Form(...),
    group_type: str = Form(..., description="warning | daily"),
    event_type: str = Form(..., description="danger | alert"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    fn = (file.filename or "").lower()
    ext = next((e for e in ALLOWED_EXTENSIONS if fn.endswith(e)), None)
    if not ext:
        raise HTTPException(400, f"지원 형식: {', '.join(ALLOWED_EXTENSIONS)}")

    raw_bytes = await file.read()
    x = _decode_audio_to_16k_mono_f32(raw_bytes, ext)

    yamnet = _get_yamnet()
    emb = yamnet.embedding_1s(x)

    # 파일 저장 (원본 확장자 유지). DB에는 "data/custom_sounds/..." 형태로 저장
    save_path = UPLOAD_DIR / f"{session_id}_{file.filename}"
    save_path.write_bytes(raw_bytes)
    audio_path_for_db = f"data/custom_sounds/{session_id}_{file.filename}"

    row = create_custom_sound(
        db=db,
        client_session_uuid=session_id,
        name=name,
        group_type=group_type,
        event_type=event_type,
        emb=emb,
        audio_path=audio_path_for_db,
    )

    return {"ok": True, "data": {"custom_sound_id": row.custom_sound_id, "name": row.name}}

def _resolve_audio_path(audio_path: str | None) -> Path | None:
    """DB에 저장된 audio_path → 실제 파일 Path. 없으면 None."""
    if not audio_path or not audio_path.strip():
        return None
    from app.Core.config import DATABASE_PATH
    p = Path(audio_path)
    if p.is_file():
        return p
    rel = audio_path.replace("\\", "/")
    if rel.startswith("data/"):
        rel = rel[5:]
    _data_dir = Path(DATABASE_PATH).resolve().parent
    full = _data_dir / rel
    return full if full.is_file() else None


@router.get("/{custom_sound_id}/audio")
def get_custom_sound_audio(
    custom_sound_id: int = ApiPath(...),
    session_id: str = Query(...),
    db: Session = Depends(get_db),
):
    """커스텀 소리 오디오 파일 스트리밍 (재생용)."""
    from app.db.crud.custom_sounds import list_custom_sounds
    rows = list_custom_sounds(db, session_id)
    row = next((r for r in rows if r.custom_sound_id == custom_sound_id), None)
    if not row:
        raise HTTPException(404, "해당 소리를 찾을 수 없거나 권한이 없습니다.")
    fp = _resolve_audio_path(row.audio_path)
    if not fp:
        raise HTTPException(404, "오디오 파일을 찾을 수 없습니다.")
    ext = fp.suffix.lower()
    media_map = {".mp3": "audio/mpeg", ".wav": "audio/wav", ".webm": "audio/webm", ".m4a": "audio/mp4"}
    media_type = media_map.get(ext, "application/octet-stream")
    return FileResponse(fp, media_type=media_type)


@router.get("")
def get_custom_sounds(
    session_id: str = Query(...),
    db: Session = Depends(get_db),
):
    rows = list_custom_sounds(db, session_id)
    return {
        "ok": True,
        "count": len(rows),
        "data": [
            {
                "custom_sound_id": r.custom_sound_id,
                "name": r.name,
                "group_type": r.group_type,
                "event_type": r.event_type,
                "audio_path": r.audio_path,
                "created_at": r.created_at,
                "updated_at": r.updated_at,
            } for r in rows
        ]
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
    deleted = delete_custom_sound(db, client_session_uuid=session_id, custom_sound_id=custom_sound_id)
    if not deleted:
        raise HTTPException(404, "해당 소리를 찾을 수 없거나 권한이 없습니다.")
    return {"ok": True}