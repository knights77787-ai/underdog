"""세션별 설정 CRUD. client_session_uuid → session_id 조회 후 settings 읽기/쓰기."""
import json

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from App.db.crud.sessions import get_or_create_by_client_uuid
from App.db.models import SettingsModel

DEFAULT_SETTINGS = {
    "font_size": 20,
    "alert_enabled": True,
    "cooldown_sec": 5,
    "auto_scroll": True,
    "beam_size": 2,  # 1=가장 빠름, 2=속도·정확 균형, 3~5=정확하지만 느려짐
    "stt_initial_prompt": "",  # 비우면 '한국어로 말합니다.' 등 프롬프트가 자막으로 안 나옴
    "stt_best_of": 0,  # 0 또는 1=가장 빠름(1회 디코딩), 2~3=정확하지만 느려짐
}


def get_settings(db: Session, client_session_uuid: str) -> dict:
    """해당 세션 설정 조회. 없으면 기본값으로 한 건 생성 후 반환."""
    sess = get_or_create_by_client_uuid(db, client_session_uuid)
    sid = sess.session_id
    row = db.query(SettingsModel).filter(SettingsModel.session_id == sid).first()
    if row is None:
        # 기본값 생성 시에도 ensure_ascii=False 로 통일
        try:
            row = SettingsModel(
                session_id=sid,
                data_json=json.dumps(DEFAULT_SETTINGS, ensure_ascii=False),
            )
            db.add(row)
            db.commit()
            db.refresh(row)
        except IntegrityError:
            # session_id 유니크라서 동시에 2번 생성 시도할 때를 대비한 레이스 방어
            db.rollback()
            row = db.query(SettingsModel).filter(SettingsModel.session_id == sid).first()
        except Exception:
            db.rollback()
            raise
    return json.loads(row.data_json)


def upsert_settings(db: Session, client_session_uuid: str, patch: dict) -> dict:
    """설정 일부만 갱신(patch). 없으면 기본값 기준으로 생성 후 merge."""
    sess = get_or_create_by_client_uuid(db, client_session_uuid)
    sid = sess.session_id
    row = db.query(SettingsModel).filter(SettingsModel.session_id == sid).first()
    if row is None:
        base = dict(DEFAULT_SETTINGS)
    else:
        base = json.loads(row.data_json)
    base.update(patch)
    data_json = json.dumps(base, ensure_ascii=False)
    if row is None:
        row = SettingsModel(session_id=sid, data_json=data_json)
        db.add(row)
    else:
        row.data_json = data_json
    try:
        db.commit()
        db.refresh(row)
    except Exception:
        db.rollback()
        raise
    return json.loads(row.data_json)
