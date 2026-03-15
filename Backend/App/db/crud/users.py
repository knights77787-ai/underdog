"""User CRUD helpers for OAuth and guest flows."""
from sqlalchemy.orm import Session

from App.db.models import User


def get_or_create_oauth_user(
    db: Session,
    provider: str,
    sub: str,
    email: str | None = None,
    name: str | None = None,
) -> User:
    """Find or create a user for given OAuth provider/sub."""
    row = (
        db.query(User)
        .filter(User.oauth_provider == provider, User.oauth_sub == sub)
        .first()
    )
    if row is not None:
        # Best-effort profile refresh
        updated = False
        if email and row.email != email:
            row.email = email
            updated = True
        if name and row.name != name:
            row.name = name
            updated = True
        if updated:
            try:
                db.commit()
                db.refresh(row)
            except Exception:
                db.rollback()
        return row

    row = User(
        oauth_provider=provider,
        oauth_sub=sub,
        email=email,
        name=name,
    )
    try:
        db.add(row)
        db.commit()
        db.refresh(row)
    except Exception:
        db.rollback()
        raise
    return row


