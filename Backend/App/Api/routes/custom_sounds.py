# App/Api/routes/custom_sounds.py
from fastapi import APIRouter, Depends, UploadFile, File, Form, Query, HTTPException
from sqlalchemy.orm import Session
from pathlib import Path
import tensorflow as tf
import numpy as np

from App.db.database import get_db
from App.db.crud.custom_sounds import create_custom_sound, list_custom_sounds
from App.Services.yamnet_service import YamnetService

router = APIRouter(prefix="/custom-sounds", tags=["custom-sounds"])

UPLOAD_DIR = Path("data/custom_sounds")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

YAMNET = YamnetService()  # 이미 앱 어딘가에서 1회 로드면 거기 재사용해도 OK

def _decode_wav_to_16k_mono_f32(wav_bytes: bytes) -> np.ndarray:
    audio, sr = tf.audio.decode_wav(wav_bytes)  # audio: (samples, channels) float32 -1..1
    audio = tf.reduce_mean(audio, axis=1)       # mono
    sr = int(sr.numpy())
    x = audio.numpy().astype(np.float32)

    if sr != 16000:
        # TF로 리샘플(간단)
        x_tf = tf.convert_to_tensor(x, dtype=tf.float32)[None, :]  # (1, N)
        new_len = int(round(x.shape[0] * (16000 / sr)))
        x_rs = tf.signal.resample(x_tf, new_len)[0].numpy().astype(np.float32)
        x = x_rs

    # 1초 윈도우로 맞추기(패드/자르기)
    if x.shape[0] < 16000:
        x = np.pad(x, (0, 16000 - x.shape[0]))
    else:
        x = x[:16000]
    return x

@router.post("")
async def upload_custom_sound(
    session_id: str = Query(..., description="클라이언트 세션 문자열 예: S1"),
    name: str = Form(...),
    group_type: str = Form(..., description="warning | daily"),
    event_type: str = Form(..., description="danger | alert"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if not file.filename.lower().endswith(".wav"):
        raise HTTPException(400, "Only .wav supported in MVP")

    wav_bytes = await file.read()
    x = _decode_wav_to_16k_mono_f32(wav_bytes)

    emb = YAMNET.embedding_1s(x)

    # 파일 저장(선택)
    save_path = UPLOAD_DIR / f"{session_id}_{file.filename}"
    save_path.write_bytes(wav_bytes)

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
            } for r in rows
        ]
    }