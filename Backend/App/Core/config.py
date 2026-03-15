"""앱 설정. event_types.json 경로, 로그 최대 개수, DB 등."""
import os
from pathlib import Path

# 관리자 API 보호용 토큰 (.env 에 ADMIN_TOKEN=... 설정)
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")

# 개발 모드: DEV=1 이면 admin 토큰 없이 /admin/* 허용 (.env 에 DEV=1)
DEV = os.getenv("DEV", "").lower() in ("1", "true", "yes")

# 프로젝트 루트(underdoc) 기준 절대 경로
# config.py: Backend/app/Core/config.py
# parents[3] -> underdoc
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
# Linux/Docker 호환: 경로 소문자(shared) 권장. 폴더명이 Shared면 shared로 통일하세요.
EVENT_TYPES_PATH = _PROJECT_ROOT / "shared" / "constants" / "event_types.json"

# SQLite: Backend 폴더 아래 data/underdog.db
_DB_DIR = Path(__file__).resolve().parents[2] / "data"
DATABASE_PATH = _DB_DIR / "underdog.db"
SQLITE_URL = f"sqlite:///{DATABASE_PATH}"

# YAMNet 공식 class map (index → display_name). TensorFlow/models 레포와 동일 포맷.
_APP_DIR = Path(__file__).resolve().parents[1]
YAMNET_CLASS_MAP_PATH = _APP_DIR / "resources" / "yamnet_class_map.csv"

MAX_CAPTIONS = 300
MAX_ALERTS = 300
DEFAULT_LOG_LIMIT = 100
MAX_LOG_LIMIT = 500
