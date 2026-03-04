"""관리자 API 보호: X-Admin-Token 헤더 검증."""
from fastapi import Header, HTTPException

from App.Core.config import ADMIN_TOKEN, DEV


def require_admin_token(x_admin_token: str = Header(default="", alias="x-admin-token")):
    """관리자 토큰이 없거나 틀리면 401/500 반환. DEV=1 이면 토큰 없이 통과."""
    if DEV:
        return  # 개발 모드: 토큰 검사 생략

    if not ADMIN_TOKEN:
        raise HTTPException(status_code=500, detail="ADMIN_TOKEN not set")

    if x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid admin token")
