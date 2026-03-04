"""세션 CRUD. 클라이언트 session_id(문자열) → DB session_id(INT) 매핑.

WS에서 오는 session_id(예: "S1" 또는 프론트에서 생성한 UUID)는
DB의 client_session_uuid 컬럼에 저장됨. 이름 혼동 방지를 위해 주석으로 명시.
"""
from sqlalchemy.orm import Session

from App.db.models import Session as SessionModel


def get_or_create_by_client_uuid(db: Session, client_session_uuid: str) -> SessionModel:
    """WS session_id 문자열(또는 UUID)로 세션 조회 또는 생성."""
    row = db.query(SessionModel).filter(
        SessionModel.client_session_uuid == client_session_uuid
    ).first()
    if row is not None:
        return row
    row = SessionModel(client_session_uuid=client_session_uuid)
    try:
        db.add(row)
        db.commit()
        db.refresh(row)
    except Exception:
        db.rollback()
        raise
    return row
