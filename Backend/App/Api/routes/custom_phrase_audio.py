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


def _decode_wav_to_16k_mono_f32(wav_bytes: bytes) -> np.ndarray:
    audio, sr = tf.audio.decode_wav(wav_bytes)  # (samples, ch) float32 -1..1
    audio = tf.reduce_mean(audio, axis=1)  # mono
    sr = int(sr.numpy())
    x = audio.numpy().astype(np.float32)

    if sr != 16000:
        x_tf = tf.convert_to_tensor(x, dtype=tf.float32)[None, :]
        new_len = int(round(x.shape[0] * (16000 / sr)))
        x_rs = tf.signal.resample(x_tf, new_len)[0].numpy().astype(np.float32)
        x = x_rs

    # 2초 정도로 고정 (과도한 길이 → 유사도 떨어짐)
    target = 16000 * 2
    if x.shape[0] < target:
        x = np.pad(x, (0, target - x.shape[0]))
    else:
        x = x[:target]
    return x


@router.post("")
async def register_phrase_audio(
    session_id: str = Query(..., description="S1 같은 클라이언트 세션"),
    name: str = Form(..., description="예: 강남역 안내"),
    event_type: str = Form(..., description="alert|danger"),
    threshold_pct: int = Form(80, ge=50, le=99, description="정규화 sim * 100 (예: 80=0.80)"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if not file.filename.lower().endswith(".wav"):
        raise HTTPException(400, "Only .wav supported in MVP")

    wav_bytes = await file.read()
    x = _decode_wav_to_16k_mono_f32(wav_bytes)

    emb = PHRASE_EMB.embed_16k_f32(x)

    save_path = UPLOAD_DIR / f"{session_id}_{file.filename}"
    save_path.write_bytes(wav_bytes)

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

