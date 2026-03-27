"""헬스체크 라우트 (마일스톤 1)."""
import os

from fastapi import APIRouter

router = APIRouter()


@router.get("/health", include_in_schema=False)
def health():
    """서버·STT 활성 여부 점검."""
    ml = os.environ.get("ENABLE_ML_WORKERS", "").strip().lower() in ("1", "true", "yes")
    api_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    stt_enabled = ml and bool(api_key)
    return {"ok": True, "stt_enabled": stt_enabled}
