"""Push endpoints (FCM token register + admin send)."""

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from App.Core.security import require_admin_token
from App.db.crud import device_tokens as crud_device_tokens
from App.db.database import get_db
from App.Services import push as push_service

router = APIRouter(prefix="/push", tags=["push"])


class RegisterTokenIn(BaseModel):
  token: str = Field(..., min_length=10)
  session_id: str | None = Field(None, description="client_session_uuid (웹/WS에서 쓰는 session_id)")
  platform: str = Field("android")
  user_id: int | None = None


@router.post("/register")
def register_token(payload: RegisterTokenIn, db: Session = Depends(get_db)):
  try:
    row = crud_device_tokens.upsert_token(
      db,
      token=payload.token,
      platform=payload.platform,
      user_id=payload.user_id,
      client_session_uuid=payload.session_id,
    )
  except ValueError as e:
    raise HTTPException(status_code=400, detail=str(e))
  return {"ok": True, "device_token_id": row.device_token_id}


class SendToSessionIn(BaseModel):
  session_id: str = Field(..., min_length=1)
  title: str = Field(..., min_length=1)
  body: str = Field("", description="notification body")
  url: str | None = Field(None, description="click url (data.url)")


@router.post("/send/session", dependencies=[Depends(require_admin_token)])
def send_to_session(payload: SendToSessionIn, db: Session = Depends(get_db)):
  rows = crud_device_tokens.list_tokens_for_session(db, client_session_uuid=payload.session_id, platform="android")
  tokens = [r.token for r in rows if r.token]
  if not tokens:
    return {"ok": True, "sent": 0, "detail": "no tokens"}

  data = {}
  if payload.url:
    data["url"] = payload.url
  data["title"] = payload.title
  data["body"] = payload.body

  result = push_service.send_to_tokens(tokens=tokens, title=payload.title, body=payload.body, data=data)
  return {"ok": True, "sent": result.get("success", 0), "failure": result.get("failure", 0), "result": result}


class SendToTokenIn(BaseModel):
  token: str = Field(..., min_length=10)
  title: str = Field(..., min_length=1)
  body: str = Field("", description="notification body")
  url: str | None = Field(None)


@router.post("/send/token", dependencies=[Depends(require_admin_token)])
def send_to_token(payload: SendToTokenIn):
  data = {"title": payload.title, "body": payload.body}
  if payload.url:
    data["url"] = payload.url
  message_id = push_service.send_to_token(token=payload.token, title=payload.title, body=payload.body, data=data)
  return {"ok": True, "message_id": message_id}

