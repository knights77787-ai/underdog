"""커스텀 구문(Whisper embedding 기반) 등록/조회 CRUD."""

from __future__ import annotations

import numpy as np
from sqlalchemy.orm import Session

from App.db.crud.embed_codec import blob_to_emb, emb_to_blob
from App.db.models import CustomPhraseAudio

def create_phrase(
    db: Session,
    client_session_uuid: str,
    name: str,
    event_type: str,
    threshold_pct: int,
    emb: np.ndarray,
    audio_path: str | None = None,
) -> CustomPhraseAudio:
    blob, dim = emb_to_blob(emb)
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

