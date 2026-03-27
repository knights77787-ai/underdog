"""커스텀 구문 오디오 등록·조회. TensorFlow는 해당 API 호출 시에만 지연 로드 (Render 메모리 절감)."""
from pathlib import Path

import numpy as np
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.orm import Session

from App.Services.audio_io import decode_audio_to_16k_mono_f32
from App.db.crud.custom_phrase_audio import create_phrase, list_phrases
from App.db.database import get_db
from App.Services.whisper_embed import PHRASE_EMB

router = APIRouter(prefix="/custom-phrase-audio", tags=["custom-phrase-audio"])

UPLOAD_DIR = Path("data/custom_phrase_audio")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = (".wav", ".mp3")
TARGET_SAMPLES = 16000 * 2  # 2초

@router.post("")
async def register_phrase_audio(
    session_id: str = Query(..., description="S1 같은 클라이언트 세션"),
    name: str = Form(..., description="예: 강남역 안내"),
    event_type: str = Form(..., description="danger | caution | alert"),
    threshold_pct: int = Form(80, ge=50, le=99, description="정규화 sim * 100 (예: 80=0.80)"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    fn = (file.filename or "").lower()
    ext = next((e for e in ALLOWED_EXTENSIONS if fn.endswith(e)), None)
    if not ext:
        raise HTTPException(400, f"지원 형식: {', '.join(ALLOWED_EXTENSIONS)}")

    raw_bytes = await file.read()
    x = decode_audio_to_16k_mono_f32(raw_bytes, ext, allowed_extensions=ALLOWED_EXTENSIONS)
    if x.shape[0] < TARGET_SAMPLES:
        x = np.pad(x, (0, TARGET_SAMPLES - x.shape[0]))
    else:
        x = x[:TARGET_SAMPLES]

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

