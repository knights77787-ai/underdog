"""Device token CRUD (FCM)."""

from sqlalchemy.orm import Session

from App.db.models import DeviceToken


def upsert_token(
    db: Session,
    *,
    token: str,
    platform: str = "android",
    user_id: int | None = None,
    client_session_uuid: str | None = None,
) -> DeviceToken:
    token = (token or "").strip()
    if not token:
        raise ValueError("token is required")

    row = db.query(DeviceToken).filter(DeviceToken.token == token).first()
    if row is None:
        row = DeviceToken(
            token=token,
            platform=platform,
            user_id=user_id,
            client_session_uuid=client_session_uuid,
        )
        try:
            db.add(row)
            db.commit()
            db.refresh(row)
        except Exception:
            db.rollback()
            raise
        return row

    changed = False
    if platform and row.platform != platform:
        row.platform = platform
        changed = True
    if row.user_id != user_id:
        row.user_id = user_id
        changed = True
    if row.client_session_uuid != client_session_uuid:
        row.client_session_uuid = client_session_uuid
        changed = True

    if changed:
        try:
            db.commit()
            db.refresh(row)
        except Exception:
            db.rollback()
            raise
    return row


def list_tokens_for_session(
    db: Session,
    *,
    client_session_uuid: str,
    platform: str | None = None,
) -> list[DeviceToken]:
    q = db.query(DeviceToken).filter(DeviceToken.client_session_uuid == client_session_uuid)
    if platform:
        q = q.filter(DeviceToken.platform == platform)
    return list(q.all())

