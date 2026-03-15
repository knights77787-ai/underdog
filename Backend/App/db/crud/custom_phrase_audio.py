"""커스텀 구문(Whisper embedding 기반) 등록/조회 CRUD."""

from __future__ import annotations

import numpy as np
from sqlalchemy.orm import Session

from app.db.models import CustomPhraseAudio


def _emb_to_blob(emb: np.ndarray) -> tuple[bytes, int]:
    emb = emb.astype(np.float32)
    return emb.tobytes(), emb.shape[0]


def _blob_to_emb(blob: bytes, dim: int) -> np.ndarray:
    return np.frombuffer(blob, dtype=np.float32, count=dim)


def create_phrase(
    db: Session,
    client_session_uuid: str,
    name: str,
    event_type: str,
    threshold_pct: int,
    emb: np.ndarray,
    audio_path: str | None = None,
) -> CustomPhraseAudio:
    blob, dim = _emb_to_blob(emb)
    row = CustomPhraseAudio(
        client_session_uuid=client_session_uuid,
        name=name,
        event_type=event_type,
        threshold_pct=threshold_pct,
        audio_path=audio_path,
        embed_dim=dim,
        embed_blob=blob,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_phrases(db: Session, client_session_uuid: str) -> list[CustomPhraseAudio]:
    return (
        db.query(CustomPhraseAudio)
        .filter(CustomPhraseAudio.client_session_uuid == client_session_uuid)
        .order_by(CustomPhraseAudio.custom_phrase_id.desc())
        .all()
    )

