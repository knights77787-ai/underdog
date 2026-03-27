from __future__ import annotations

"""커스텀 사운드 CRUD 및 embedding 직렬화."""

from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
from sqlalchemy import or_
from sqlalchemy.orm import Session

from App.Core.config import CUSTOM_SOUND_AUDIO_RETENTION_HOURS, DATABASE_PATH
from App.db.models import CustomSound


def resolve_custom_sound_disk_path(audio_path: str | None) -> Path | None:
    """DB audio_path 문자열 → 실제 파일 Path. 없으면 None."""
    if not audio_path or not audio_path.strip():
        return None
    p = Path(audio_path)
    if p.is_file():
        return p
    rel = audio_path.replace("\\", "/")
    if rel.startswith("data/"):
        rel = rel[5:]
    _data_dir = Path(DATABASE_PATH).resolve().parent
    full = _data_dir / rel
    return full if full.is_file() else None


def maybe_expire_custom_sound_audio(db: Session, row: CustomSound) -> bool:
    """
    보관 기간이 지난 원본이면 디스크에서 삭제하고 audio_path 를 NULL 로 갱신.
    커밋까지 수행. 임베딩·메타는 유지.
    Returns: True if row had audio and it was expired (cleared), else False.
    """
    if not row.audio_path:
        return False
    deadline = row.created_at + timedelta(hours=CUSTOM_SOUND_AUDIO_RETENTION_HOURS)
    if datetime.utcnow() <= deadline:
        return False
    p = resolve_custom_sound_disk_path(row.audio_path)
    if p and p.is_file():
        try:
            p.unlink()
        except OSError:
            pass
    row.audio_path = None
    db.add(row)
    db.commit()
    return True


def expire_stale_custom_sounds_audio_for_session(db: Session, client_session_uuid: str) -> None:
    """해당 세션의 커스텀 소리 중 만료된 원본을 일괄 정리."""
    rows = (
        db.query(CustomSound)
        .filter(CustomSound.client_session_uuid == client_session_uuid)
        .all()
    )
    changed = False
    now = datetime.utcnow()
    for r in rows:
        if not r.audio_path:
            continue
        if now <= r.created_at + timedelta(hours=CUSTOM_SOUND_AUDIO_RETENTION_HOURS):
            continue
        p = resolve_custom_sound_disk_path(r.audio_path)
        if p and p.is_file():
            try:
                p.unlink()
            except OSError:
                pass
        r.audio_path = None
        changed = True
    if changed:
        db.commit()


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
    event_type: str,
    emb: np.ndarray,
    audio_path: str | None = None,
    user_id: int | None = None,
    match_threshold: float | None = None,
) -> CustomSound:
    """커스텀 사운드 1건 생성."""
    blob, dim = _emb_to_blob(emb)
    row = CustomSound(
        client_session_uuid=client_session_uuid,
        name=name,
        event_type=event_type,
        audio_path=audio_path,
        embed_dim=dim,
        embed_blob=blob,
        user_id=user_id,
        match_threshold=match_threshold,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_custom_sounds(
    db: Session,
    client_session_uuid: str,
    user_id: int | None = None,
) -> list[CustomSound]:
    """커스텀 사운드 목록 조회.

    - guest: client_session_uuid 기준
    - login user: user_id 기준(과거 동일 세션 등록도 함께 보여주기 위해 OR로 보강)
    """
    q = db.query(CustomSound)
    if user_id is not None:
        q = q.filter(
            or_(
                CustomSound.user_id == user_id,
                CustomSound.client_session_uuid == client_session_uuid,
            )
        )
    else:
        q = q.filter(CustomSound.client_session_uuid == client_session_uuid)
    return q.order_by(CustomSound.custom_sound_id.desc()).all()


def delete_custom_sound(
    db: Session,
    client_session_uuid: str,
    custom_sound_id: int,
    user_id: int | None = None,
) -> bool:
    """
    커스텀 사운드 1건 삭제 (DB + 파일). 세션 소유권을 함께 확인.
    Returns: True if deleted, False if not found (wrong session or already deleted).
    """
    q = db.query(CustomSound).filter(CustomSound.custom_sound_id == custom_sound_id)
    if user_id is not None:
        q = q.filter(
            or_(
                CustomSound.user_id == user_id,
                CustomSound.client_session_uuid == client_session_uuid,
            )
        )
    else:
        q = q.filter(CustomSound.client_session_uuid == client_session_uuid)
    row: CustomSound | None = q.first()
    if row is None:
        return False

    # 오디오 파일이 있으면 함께 삭제 (없거나 실패해도 계속 진행)
    if row.audio_path:
        try:
            p = resolve_custom_sound_disk_path(row.audio_path)
            if p and p.is_file():
                p.unlink()
        except Exception:
            pass

    db.delete(row)
    db.commit()
    return True

