"""OAuth (Google, Kakao) + Guest login + Admin login endpoints."""
import os
from typing import Literal
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Body, Depends, HTTPException, Request, Query
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
from sqlalchemy.orm import Session

from App.Core.config import ADMIN_TOKEN, DEV
from App.db.crud import sessions as crud_sessions
from App.db.crud import users as crud_users
from App.db.database import get_db

router = APIRouter(prefix="/auth", tags=["auth"])

# 관리자 로그인용 쿠키 설정
ADMIN_COOKIE_NAME = "admin_token"
ADMIN_COOKIE_MAX_AGE = 60 * 60 * 24  # 24시간


def _redirect_uri_from_request(request: Request, path: str) -> str:
    """요청 Host 기반 redirect_uri 생성. 에뮬레이터(10.0.2.2) / PC(localhost) 모두 대응."""
    base = str(request.base_url).rstrip("/")
    return f"{base}{path}"


def _get_redirect_uri(request: Request, env_key: str, path: str) -> str:
    """env에 설정된 redirect_uri 사용(Google/Kakao 콘솔과 일치). 없으면 요청 기반 생성."""
    env_uri = os.getenv(env_key, "").strip()
    if env_uri:
        return env_uri
    return _redirect_uri_from_request(request, path)


Provider = Literal["google", "kakao"]


def _create_session_payload(
    provider: Provider | Literal["guest"],
    client_session_uuid: str,
    user_id: int | None = None,
    name: str | None = None,
    email: str | None = None,
) -> dict:
    return {
        "ok": True,
        "session_id": client_session_uuid,
        "user": {
            "id": user_id,
            "name": name,
            "email": email,
            "provider": provider,
        },
    }


def _success_redirect_response(
    request: Request, payload: dict, *, mobile: bool = False
) -> RedirectResponse | HTMLResponse:
    """After successful OAuth, redirect to frontend with session info in query.

    mobile=True: 모바일 앱용 → /auth/mobile-done 로 리다이렉트 (앱 딥링크 페이지).
    else: FRONTEND_AUTH_REDIRECT_URL 환경변수로 경로 지정.
    """
    session_id = payload["session_id"]
    provider = payload["user"]["provider"]

    if mobile:
        base = str(request.base_url).rstrip("/")
        url = f"{base}/auth/mobile-done?session_id={session_id}&provider={provider}"
        return RedirectResponse(url)

    path = os.getenv("FRONTEND_AUTH_REDIRECT_URL", "/").strip()
    if path.startswith("http://") or path.startswith("https://"):
        parsed = urlparse(path)
        if "127.0.0.1" in path or "localhost" in path:
            path_part = parsed.path or "/"
            base = str(request.base_url).rstrip("/") + path_part
        else:
            base = path.rstrip("/")
    else:
        base = str(request.base_url).rstrip("/") + (path if path.startswith("/") else "/" + path)
    sep = "&" if "?" in base else "?"
    url = f"{base}{sep}session_id={session_id}&provider={provider}"
    return RedirectResponse(url)


#
# Google OAuth
#

@router.get("/google/login")
async def google_login(request: Request, mobile: bool = Query(False, description="모바일 앱: 1이면 콜백 후 /auth/mobile-done으로 리다이렉트")):
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    if not client_id:
        raise HTTPException(
            status_code=500,
            detail="Google OAuth is not configured (GOOGLE_CLIENT_ID)",
        )
    redirect_uri = _get_redirect_uri(request, "GOOGLE_REDIRECT_URI", "/auth/google/callback")

    auth_url = "https://accounts.google.com/o/oauth2/v2/auth"
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
    }
    if mobile:
        params["state"] = "mobile"
    url = httpx.URL(auth_url, params=params)
    return RedirectResponse(str(url))


@router.get("/google/callback")
async def google_callback(
    request: Request,
    code: str,
    state: str | None = Query(None),
    db: Session = Depends(get_db),
):
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise HTTPException(
            status_code=500,
            detail="Google OAuth is not configured (GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET)",
        )
    # login 시 사용한 redirect_uri와 동일해야 함 (env 우선)
    redirect_uri = _get_redirect_uri(request, "GOOGLE_REDIRECT_URI", "/auth/google/callback")

    token_url = "https://oauth2.googleapis.com/token"
    userinfo_url = "https://www.googleapis.com/oauth2/v3/userinfo"

    async with httpx.AsyncClient(timeout=10.0) as client:
        token_res = await client.post(
            token_url,
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        if token_res.status_code != 200:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to get Google access token ({token_res.status_code})",
            )
        token = token_res.json()
        access_token = token.get("access_token")
        if not access_token:
            raise HTTPException(status_code=400, detail="No access_token in Google response")

        user_res = await client.get(
            userinfo_url,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if user_res.status_code != 200:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to fetch Google user info ({user_res.status_code})",
            )
        info = user_res.json()

    oauth_provider: Provider = "google"
    oauth_sub = info.get("sub")
    if not oauth_sub:
        raise HTTPException(status_code=400, detail="Google userinfo missing 'sub'")

    email = info.get("email")
    name = info.get("name")

    user = crud_users.get_or_create_oauth_user(
        db,
        provider=oauth_provider,
        sub=oauth_sub,
        email=email,
        name=name,
    )
    session = crud_sessions.create_session_for_user(
        db,
        user_id=user.user_id,
        is_guest=False,
    )
    payload = _create_session_payload(
        provider=oauth_provider,
        client_session_uuid=session.client_session_uuid or "",
        user_id=user.user_id,
        name=user.name,
        email=user.email,
    )
    return _success_redirect_response(request, payload, mobile=(state == "mobile"))


#
# Kakao OAuth
#

@router.get("/kakao/login")
async def kakao_login(request: Request, mobile: bool = Query(False, description="모바일 앱: 1이면 콜백 후 /auth/mobile-done으로 리다이렉트")):
    client_id = os.getenv("KAKAO_CLIENT_ID")
    if not client_id:
        raise HTTPException(
            status_code=500,
            detail="Kakao OAuth is not configured (KAKAO_CLIENT_ID)",
        )
    redirect_uri = _get_redirect_uri(request, "KAKAO_REDIRECT_URI", "/auth/kakao/callback")

    auth_url = "https://kauth.kakao.com/oauth/authorize"
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "profile_nickname,account_email",
    }
    if mobile:
        params["state"] = "mobile"
    url = httpx.URL(auth_url, params=params)
    return RedirectResponse(str(url))


@router.get("/kakao/callback")
async def kakao_callback(
    request: Request,
    code: str,
    state: str | None = Query(None),
    db: Session = Depends(get_db),
):
    client_id = os.getenv("KAKAO_CLIENT_ID")
    client_secret = os.getenv("KAKAO_CLIENT_SECRET", "")
    if not client_id:
        raise HTTPException(
            status_code=500,
            detail="Kakao OAuth is not configured (KAKAO_CLIENT_ID)",
        )
    redirect_uri = _get_redirect_uri(request, "KAKAO_REDIRECT_URI", "/auth/kakao/callback")

    token_url = "https://kauth.kakao.com/oauth/token"
    userinfo_url = "https://kapi.kakao.com/v2/user/me"

    async with httpx.AsyncClient(timeout=10.0) as client:
        token_res = await client.post(
            token_url,
            data={
                "grant_type": "authorization_code",
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "code": code,
                "client_secret": client_secret,
            },
        )
        if token_res.status_code != 200:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to get Kakao access token ({token_res.status_code})",
            )
        token = token_res.json()
        access_token = token.get("access_token")
        if not access_token:
            raise HTTPException(status_code=400, detail="No access_token in Kakao response")

        user_res = await client.get(
            userinfo_url,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if user_res.status_code != 200:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to fetch Kakao user info ({user_res.status_code})",
            )
        info = user_res.json()

    kakao_id = info.get("id")
    if kakao_id is None:
        raise HTTPException(status_code=400, detail="Kakao userinfo missing 'id'")

    kakao_account = info.get("kakao_account", {}) or {}
    profile = kakao_account.get("profile", {}) or {}

    oauth_provider: Provider = "kakao"
    oauth_sub = str(kakao_id)
    email = kakao_account.get("email") or kakao_account.get("email_address")
    name = (
        profile.get("nickname")
        or kakao_account.get("name")
        or kakao_account.get("profile_nickname")
    )

    user = crud_users.get_or_create_oauth_user(
        db,
        provider=oauth_provider,
        sub=oauth_sub,
        email=email,
        name=name,
    )
    session = crud_sessions.create_session_for_user(
        db,
        user_id=user.user_id,
        is_guest=False,
    )
    payload = _create_session_payload(
        provider=oauth_provider,
        client_session_uuid=session.client_session_uuid or "",
        user_id=user.user_id,
        name=user.name,
        email=user.email,
    )
    return _success_redirect_response(request, payload, mobile=(state == "mobile"))


@router.get("/mobile-done", response_class=HTMLResponse)
async def auth_mobile_done(
    session_id: str = Query(..., description="세션 ID (앱으로 전달)"),
    provider: str = Query(..., description="google | kakao"),
):
    """모바일 앱 OAuth 완료 후 이 페이지로 리다이렉트됨. underdog:// 딥링크로 앱을 연다."""
    # 앱 scheme (Expo app.json scheme과 일치)
    app_url = f"underdog://live?session_id={session_id}&provider={provider}"
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>로그인 완료</title></head>
<body>
<p>로그인되었습니다. 앱으로 돌아가세요.</p>
<script>window.location.href = {repr(app_url)};</script>
<noscript><a href="{app_url}">앱 열기</a></noscript>
</body></html>"""
    return HTMLResponse(html)


#
# 현재 로그인 사용자 정보 (OAuth 로그인 시에만, session_id로 조회)
#

@router.get("/me")
def get_me(
    session_id: str = Query(..., description="client_session_uuid (URL의 session_id)"),
    db: Session = Depends(get_db),
):
    """로그인한 사용자(Google/Kakao)의 name, email 반환. 게스트/미존재 시 404."""
    from App.db.models import Session as SessionModel, User

    sess = (
        db.query(SessionModel)
        .filter(SessionModel.client_session_uuid == session_id)
        .first()
    )
    if not sess or sess.user_id is None:
        raise HTTPException(status_code=404, detail="User not found or guest session")
    user = db.query(User).filter(User.user_id == sess.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "ok": True,
        "name": user.name or "",
        "email": user.email or "",
    }


#
# Guest login
#

@router.post("/guest")
def guest_login(db: Session = Depends(get_db)):
    """Create a guest session and return session_id.

    게스트는 User 레코드 없이 Session에 is_guest=True 로만 저장합니다.
    """
    session = crud_sessions.create_guest_session(db)
    payload = _create_session_payload(
        provider="guest",
        client_session_uuid=session.client_session_uuid or "",
        user_id=None,
        name=None,
        email=None,
    )
    return JSONResponse(payload)


#
# Admin login (토큰 검증 + 쿠키 발급)
#

@router.post("/admin/login")
async def admin_login(
    token: str = Body(..., embed=True),
):
    """관리자 토큰 검증 후 쿠키 발급. 성공 시 /admin 페이지로 리다이렉트."""
    if DEV:
        # 개발 모드: 토큰 없어도 통과 (빈 값 허용)
        redirect = RedirectResponse(url="/admin", status_code=302)
        redirect.set_cookie(
            key=ADMIN_COOKIE_NAME,
            value=token or "dev-bypass",
            max_age=ADMIN_COOKIE_MAX_AGE,
            httponly=True,
            samesite="lax",
        )
        return redirect

    if not ADMIN_TOKEN:
        raise HTTPException(status_code=500, detail="ADMIN_TOKEN not set")

    if not token or (token.strip() != ADMIN_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid admin token")

    redirect = RedirectResponse(url="/admin", status_code=302)
    redirect.set_cookie(
        key=ADMIN_COOKIE_NAME,
        value=token.strip(),
        max_age=ADMIN_COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
    )
    return redirect


@router.post("/admin/logout")
async def admin_logout():
    """관리자 쿠키 삭제 후 로그인 페이지로 리다이렉트."""
    redirect = RedirectResponse(url="/admin-login", status_code=302)
    redirect.delete_cookie(key=ADMIN_COOKIE_NAME)
    return redirect

