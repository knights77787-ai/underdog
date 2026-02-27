"""헬스체크 라우트 (마일스톤 1)."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health():
    return {"ok": True}
