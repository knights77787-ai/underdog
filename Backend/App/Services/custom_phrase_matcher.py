"""Whisper embedding 기반 커스텀 안내 음성 매칭."""

from __future__ import annotations

import numpy as np

from App.Services.whisper_embed import PHRASE_EMB


def match_phrase(session_id: str, speech_audio_16k_f32: np.ndarray):
    """세션별 CustomPhraseAudio 중 speech_audio와 가장 유사한 항목 찾기.

    Returns:
        (row or None, sim: float)
    """
    from App.db.database import SessionLocal
    from App.db.crud.embed_codec import blob_to_emb
    from App.db.models import CustomPhraseAudio

    emb_live = PHRASE_EMB.embed_16k_f32(speech_audio_16k_f32)

    db = SessionLocal()
    try:
        rows = (
            db.query(CustomPhraseAudio)
            .filter(CustomPhraseAudio.client_session_uuid == session_id)
            .all()
        )
        best = None
        best_sim = 0.0
        for r in rows:
            if not r.embed_blob or not r.embed_dim:
                continue
            emb = blob_to_emb(r.embed_blob, r.embed_dim)
            sim = float(np.dot(emb_live, emb))
            if sim > best_sim:
                best_sim = sim
                best = r
        return best, best_sim
    finally:
        db.close()

