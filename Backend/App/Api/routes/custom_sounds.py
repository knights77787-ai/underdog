# App/Api/routes/custom_sounds.py
import io
from pathlib import Path

import numpy as np
import tensorflow as tf
from fastapi import APIRouter, Depends, File, Form, HTTPException, Path as ApiPath, Query, UploadFile
from sqlalchemy.orm import Session

from App.db.crud.custom_sounds import (
    create_custom_sound,
    list_custom_sounds,
    delete_custom_sound,
)
from App.db.database import get_db
from App.Services.yamnet_service import YamnetService

from scipy.signal import resample

router = APIRouter(prefix="/custom-sounds", tags=["custom-sounds"])

UPLOAD_DIR = Path("data/custom_sounds")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

YAMNET = YamnetService()  # 이미 앱 어딘가에서 1회 로드면 거기 재사용해도 OK

ALLOWED_EXTENSIONS = (".wav", ".mp3")

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

def _decode_mp3_to_16k_mono_f32(mp3_bytes: bytes) -> np.ndarray:
    try:
        from pydub import AudioSegment
    except ImportError:
        raise HTTPException(
            503,
            "MP3 지원을 위해 pydub 패키지가 필요합니다. pip install pydub 및 (선택) ffmpeg 설치 후 이용하세요.",
        )
    try:
        seg = AudioSegment.from_file(io.BytesIO(mp3_bytes), format="mp3")
    except Exception as e:
        raise HTTPException(400, f"MP3 디코딩 실패. ffmpeg 설치 여부를 확인하세요: {e!s}")
    seg = seg.set_channels(1)
    sr = seg.frame_rate
    samples = np.array(seg.get_array_of_samples(), dtype=np.float32) / 32768.0
    samples = _resample_to_16k(samples, sr)
    return _normalize_1s_window(samples)

def _decode_audio_to_16k_mono_f32(data: bytes, ext: str) -> np.ndarray:
    ext = ext.lower()
    if ext == ".wav":
        return _decode_wav_to_16k_mono_f32(data)
    if ext == ".mp3":
        return _decode_mp3_to_16k_mono_f32(data)
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

    emb = YAMNET.embedding_1s(x)

    # 파일 저장 (원본 확장자 유지)
    save_path = UPLOAD_DIR / f"{session_id}_{file.filename}"
    save_path.write_bytes(raw_bytes)

    row = create_custom_sound(
        db=db,
        client_session_uuid=session_id,
        name=name,
        group_type=group_type,
        event_type=event_type,
        emb=emb,
        audio_path=str(save_path),
    )

    return {"ok": True, "data": {"custom_sound_id": row.custom_sound_id, "name": row.name}}

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