import io
from pathlib import Path

import numpy as np
import tensorflow as tf
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from App.db.crud.custom_phrase_audio import create_phrase, list_phrases
from App.db.database import get_db
from App.Services.whisper_embed import PHRASE_EMB

router = APIRouter(prefix="/custom-phrase-audio", tags=["custom-phrase-audio"])

UPLOAD_DIR = Path("data/custom_phrase_audio")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = (".wav", ".mp3")
TARGET_SAMPLES = 16000 * 2  # 2초


def _resample_to_16k(x: np.ndarray, sr: int) -> np.ndarray:
    if sr == 16000:
        return x
    x_tf = tf.convert_to_tensor(x, dtype=tf.float32)[None, :]
    new_len = int(round(x.shape[0] * (16000 / sr)))
    return tf.signal.resample(x_tf, new_len)[0].numpy().astype(np.float32)


def _decode_wav_to_16k_mono_f32(wav_bytes: bytes) -> np.ndarray:
    audio, sr = tf.audio.decode_wav(wav_bytes)
    audio = tf.reduce_mean(audio, axis=1)
    sr = int(sr.numpy())
    x = audio.numpy().astype(np.float32)
    x = _resample_to_16k(x, sr)
    if x.shape[0] < TARGET_SAMPLES:
        x = np.pad(x, (0, TARGET_SAMPLES - x.shape[0]))
    else:
        x = x[:TARGET_SAMPLES]
    return x


def _decode_mp3_to_16k_mono_f32(mp3_bytes: bytes) -> np.ndarray:
    try:
        from pydub import AudioSegment
    except ImportError:
        raise HTTPException(503, "MP3 지원을 위해 pydub 설치가 필요합니다: pip install pydub")
    try:
        seg = AudioSegment.from_file(io.BytesIO(mp3_bytes), format="mp3")
    except Exception as e:
        raise HTTPException(400, f"MP3 디코딩 실패 (ffmpeg 설치 확인): {e!s}")
    seg = seg.set_channels(1)
    sr = seg.frame_rate
    x = np.array(seg.get_array_of_samples(), dtype=np.float32) / 32768.0
    x = _resample_to_16k(x, sr)
    if x.shape[0] < TARGET_SAMPLES:
        x = np.pad(x, (0, TARGET_SAMPLES - x.shape[0]))
    else:
        x = x[:TARGET_SAMPLES]
    return x


def _decode_audio_to_16k_mono_f32(data: bytes, ext: str) -> np.ndarray:
    ext = ext.lower()
    if ext == ".wav":
        return _decode_wav_to_16k_mono_f32(data)
    if ext == ".mp3":
        return _decode_mp3_to_16k_mono_f32(data)
    raise HTTPException(400, f"지원 형식: {', '.join(ALLOWED_EXTENSIONS)}")


@router.post("")
async def register_phrase_audio(
    session_id: str = Query(..., description="S1 같은 클라이언트 세션"),
    name: str = Form(..., description="예: 강남역 안내"),
    event_type: str = Form(..., description="alert|danger"),
    threshold_pct: int = Form(80, ge=50, le=99, description="정규화 sim * 100 (예: 80=0.80)"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    fn = (file.filename or "").lower()
    ext = next((e for e in ALLOWED_EXTENSIONS if fn.endswith(e)), None)
    if not ext:
        raise HTTPException(400, f"지원 형식: {', '.join(ALLOWED_EXTENSIONS)}")

    raw_bytes = await file.read()
    x = _decode_audio_to_16k_mono_f32(raw_bytes, ext)

    emb = PHRASE_EMB.embed_16k_f32(x)

    save_path = UPLOAD_DIR / f"{session_id}_{file.filename}"
    save_path.write_bytes(raw_bytes)

    row = create_phrase(
        db=db,
        client_session_uuid=session_id,
        name=name,
        event_type=event_type,
        threshold_pct=threshold_pct,
        emb=emb,
        audio_path=str(save_path),
    )

    return {"ok": True, "data": {"custom_phrase_id": row.custom_phrase_id, "name": row.name}}


@router.get("")
def get_phrases(
    session_id: str = Query(...),
    db: Session = Depends(get_db),
):
    rows = list_phrases(db, session_id)
    return {
        "ok": True,
        "count": len(rows),
        "data": [
            {
                "custom_phrase_id": r.custom_phrase_id,
                "name": r.name,
                "event_type": r.event_type,
                "threshold_pct": r.threshold_pct,
            }
            for r in rows
        ],
    }

