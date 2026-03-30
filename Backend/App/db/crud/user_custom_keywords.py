from __future__ import annotations

from sqlalchemy.orm import Session

from App.db.crud.sessions import get_or_create_by_client_uuid
from App.db.models import Session as SessionModel
from App.db.models import UserCustomKeyword

_VALID_EVENT_TYPES = frozenset({"danger", "caution", "alert"})


def _resolve_user_id_from_session(db: Session, client_session_uuid: str) -> int | None:
    row = (
        db.query(SessionModel)
        .filter(SessionModel.client_session_uuid == client_session_uuid)
        .first()
    )
    return int(row.user_id) if row and row.user_id is not None else None


def _norm_phrase(s: str) -> str:
    return (s or "").strip().lower()


def _iter_session_rows(db: Session, client_session_uuid: str):
    user_id = _resolve_user_id_from_session(db, client_session_uuid)
    q = db.query(UserCustomKeyword)
    if user_id is not None:
        q = q.filter(UserCustomKeyword.user_id == user_id)
    else:
        q = q.filter(
            UserCustomKeyword.client_session_uuid == client_session_uuid,
            UserCustomKeyword.user_id.is_(None),
        )
    return q.order_by(UserCustomKeyword.user_custom_keyword_id.asc())


def phrase_exists_for_session(db: Session, client_session_uuid: str, phrase: str) -> bool:
    n = _norm_phrase(phrase)
    if not n:
        return False
    for r in _iter_session_rows(db, client_session_uuid).all():
        if _norm_phrase(r.phrase) == n:
            return True
    return False


def list_rules_for_session(
    db: Session, client_session_uuid: str
) -> list[tuple[str, str, str]]:
    """(phrase, event_type, canonical) — canonical은 표시용으로 phrase와 동일."""
    out: list[tuple[str, str, str]] = []
    for r in _iter_session_rows(db, client_session_uuid).all():
        out.append((r.phrase, r.event_type, r.phrase))
    return out


def create_user_custom_keyword(
    db: Session,
    client_session_uuid: str,
    phrase: str,
    event_type: str,
) -> UserCustomKeyword:
    et = (event_type or "").strip().lower()
    if et not in _VALID_EVENT_TYPES:
        raise ValueError("invalid_event_type")
    cleaned = (phrase or "").strip()
    if not cleaned:
        raise ValueError("empty_phrase")
    if len(cleaned) > 255:
        raise ValueError("phrase_too_long")
    if phrase_exists_for_session(db, client_session_uuid, cleaned):
        raise ValueError("duplicate_phrase")
    sess = get_or_create_by_client_uuid(db, client_session_uuid)
    row = UserCustomKeyword(
        user_id=sess.user_id,
        client_session_uuid=client_session_uuid,
        phrase=cleaned,
        event_type=et,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
