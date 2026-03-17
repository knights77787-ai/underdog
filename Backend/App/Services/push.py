"""FCM push helpers (firebase-admin).

Set env:
- FIREBASE_SERVICE_ACCOUNT_PATH=/abs/path/to/service-account.json
"""

from __future__ import annotations

import os
from typing import Any

from App.Core.logging import get_logger

_log = get_logger("push")

_firebase_initialized = False


def _ensure_firebase() -> None:
  global _firebase_initialized
  if _firebase_initialized:
    return

  service_account_path = (os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH") or "").strip()
  if not service_account_path:
    raise RuntimeError("FIREBASE_SERVICE_ACCOUNT_PATH is not set")

  try:
    import firebase_admin
    from firebase_admin import credentials
  except Exception as e:  # pragma: no cover
    raise RuntimeError("firebase-admin is not installed") from e

  if firebase_admin._apps:
    _firebase_initialized = True
    return

  cred = credentials.Certificate(service_account_path)
  firebase_admin.initialize_app(cred)
  _firebase_initialized = True
  _log.info("firebase initialized with service account: %s", service_account_path)


def send_to_token(
  *,
  token: str,
  title: str,
  body: str,
  data: dict[str, str] | None = None,
) -> str:
  _ensure_firebase()
  from firebase_admin import messaging

  msg = messaging.Message(
    token=token,
    notification=messaging.Notification(title=title, body=body),
    data=data or {},
    android=messaging.AndroidConfig(priority="high"),
  )
  return messaging.send(msg)


def send_to_tokens(
  *,
  tokens: list[str],
  title: str,
  body: str,
  data: dict[str, str] | None = None,
) -> dict[str, Any]:
  _ensure_firebase()
  from firebase_admin import messaging

  if not tokens:
    return {"success": 0, "failure": 0, "responses": []}

  msg = messaging.MulticastMessage(
    tokens=tokens,
    notification=messaging.Notification(title=title, body=body),
    data=data or {},
    android=messaging.AndroidConfig(priority="high"),
  )
  resp = messaging.send_each_for_multicast(msg)
  return {
    "success": resp.success_count,
    "failure": resp.failure_count,
    "responses": [
      {"ok": r.success, "message_id": r.message_id, "exception": str(r.exception) if r.exception else None}
      for r in resp.responses
    ],
  }

