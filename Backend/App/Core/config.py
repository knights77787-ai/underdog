"""앱 설정. event_types.json 경로, 로그 최대 개수 등."""
from pathlib import Path

# 프로젝트 루트(underdoc) 기준 절대 경로
# config.py: Backend/App/Core/config.py
# parents[3] -> underdoc
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
EVENT_TYPES_PATH = _PROJECT_ROOT / "Shared" / "constants" / "event_types.json"

MAX_CAPTIONS = 300
MAX_ALERTS = 300
DEFAULT_LOG_LIMIT = 100
MAX_LOG_LIMIT = 500
