from __future__ import annotations

import os


def env_flag(name: str, default: bool = False) -> bool:
    """
    환경변수 플래그 파서.
    예: ENABLE_ML_WORKERS=true, 1, yes 등은 True로 처리.
    """
    raw = os.environ.get(name)
    if raw is None:
        return default
    v = raw.strip().lower()
    return v in ("1", "true", "yes", "on")


def is_heavy_workers_enabled() -> bool:
    """ENABLE_ML_WORKERS 플래그 기반."""
    return env_flag("ENABLE_ML_WORKERS", default=False)

