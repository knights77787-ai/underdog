"""로그 API 요청/응답 스키마."""
from typing import Literal

from pydantic import BaseModel, Field


class LogsQuery(BaseModel):
    type: Literal["caption", "alert", "all"] = "all"
    limit: int = Field(100, ge=1, le=500, description="최대 건수")
    session_id: str | None = None
