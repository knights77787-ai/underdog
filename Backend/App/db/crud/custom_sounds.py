from __future__ import annotations

"""커스텀 사운드 CRUD 및 embedding 직렬화."""

import numpy as np
from sqlalchemy.orm import Session

from pathlib import Path

from App.db.models import CustomSound


def _emb_to_blob(emb: np.ndarray) -> tuple[bytes, int]:
    """float32 embedding -> (blob, dim)."""
    emb = emb.astype(np.float32)
    return emb.tobytes(), emb.shape[0]


def _blob_to_emb(blob: bytes, dim: int) -> np.ndarray:
    """(blob, dim) -> float32 embedding."""
    return np.frombuffer(blob, dtype=np.float32, count=dim)


def create_custom_sound(
    db: Session,
    client_session_uuid: str,
    name: str,
    group_type: str,
    event_type: str,
    emb: np.ndarray,
    audio_path: str | None = None,
) -> CustomSound:
    """커스텀 사운드 1건 생성."""
    blob, dim = _emb_to_blob(emb)
    row = CustomSound(
        client_session_uuid=client_session_uuid,
        name=name,
        group_type=group_type,
        event_type=event_type,
        audio_path=audio_path,
        embed_dim=dim,
        embed_blob=blob,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_custom_sounds(db: Session, client_session_uuid: str) -> list[CustomSound]:
    """세션별 커스텀 사운드 목록 (최근 등록 순)."""
    return (
        db.query(CustomSound)
        .filter(CustomSound.client_session_uuid == client_session_uuid)
        .order_by(CustomSound.custom_sound_id.desc())
        .all()
    )


def delete_custom_sound(
    db: Session,
    client_session_uuid: str,
    custom_sound_id: int,
) -> bool:
    """
    커스텀 사운드 1건 삭제 (DB + 파일). 세션 소유권을 함께 확인.
    Returns: True if deleted, False if not found (wrong session or already deleted).
    """
    row: CustomSound | None = (
        db.query(CustomSound)
        .filter(
            CustomSound.custom_sound_id == custom_sound_id,
            CustomSound.client_session_uuid == client_session_uuid,
        )
        .first()
    )
    if row is None:
        return False

    # 오디오 파일이 있으면 함께 삭제 (없거나 실패해도 계속 진행)
    if row.audio_path:
        try:
            p = Path(row.audio_path)
            if not p.is_file() and not p.is_absolute():
                # 상대 경로 "data/custom_sounds/..." → Backend/data/custom_sounds/...
                from App.Core.config import DATABASE_PATH
                _data_dir = Path(DATABASE_PATH).resolve().parent
                rel = row.audio_path.replace("\\", "/")
                if rel.startswith("data/"):
                    rel = rel[5:]  # strip "data/"
                p = _data_dir / rel
            if p.is_file():
                p.unlink()
        except Exception:
            # 파일 삭제 실패는 무시 (DB 정합성을 우선)
            pass

    db.delete(row)
    db.commit()
    return True

