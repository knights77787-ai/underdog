"""앱 설정. event_types.json 경로, 로그 최대 개수, DB 등."""
import os
from pathlib import Path

# 관리자 API 보호용 토큰 (.env 에 ADMIN_TOKEN=... 설정)
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")

# 개발 모드: DEV=1 이면 admin 토큰 없이 /admin/* 허용 (.env 에 DEV=1)
DEV = os.getenv("DEV", "").lower() in ("1", "true", "yes")

# 프로젝트 루트(underdoc) 기준 절대 경로
# config.py: Backend/App/Core/config.py
# parents[3] -> underdoc
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
# Linux/Docker 호환: 리눅스는 대소문자 구분이라 shared/Shared 둘 다 지원
_EVENT_TYPES_CANDIDATES = [
    _PROJECT_ROOT / "shared" / "constants" / "event_types.json",
    _PROJECT_ROOT / "Shared" / "constants" / "event_types.json",
]
EVENT_TYPES_PATH = next((p for p in _EVENT_TYPES_CANDIDATES if p.exists()), _EVENT_TYPES_CANDIDATES[0])

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

# STT 침묵 스킵: 이 RMS 미만이면 STT로 안 보냄. 도메인(lumen.ai.kr)에서만 안 되면 0.001 또는 0/off(비활성) 설정
def _stt_silence_threshold() -> float:
    v = os.getenv("STT_SILENCE_RMS_THRESHOLD", "").strip().lower()
    if v in ("off", "0"):
        return 0.0  # 비활성: 침묵 스킵 안 함
    if v == "":
        return 0.002
    try:
        return float(v)
    except ValueError:
        return 0.002


STT_SILENCE_RMS_THRESHOLD = _stt_silence_threshold()


# 등록 원본 음원: 서버에 둘 수 있는 최장 시간(시간). 정책상 **최대 7일(168h) 초과 보관 불가**.
_CUSTOM_SOUND_AUDIO_MAX_HOURS = 168
_CUSTOM_SOUND_AUDIO_MIN_HOURS = 24


def _custom_sound_audio_retention_hours() -> int:
    """
    커스텀 소리 등록 시 업로드 원본 파일을 디스크에 둘 수 있는 시간(시간 단위).
    - 기본 168시간(7일). 7일 경과 후 원본 파일은 반드시 삭제·미보관(임베딩만 유지).
    - 환경변수 CUSTOM_SOUND_AUDIO_RETENTION_HOURS: **24 이상 168 이하**만 허용(더 길게 두는 설정은 불가).
    """
    raw = os.getenv("CUSTOM_SOUND_AUDIO_RETENTION_HOURS", "").strip()
    if raw:
        try:
            h = int(raw)
            return max(_CUSTOM_SOUND_AUDIO_MIN_HOURS, min(h, _CUSTOM_SOUND_AUDIO_MAX_HOURS))
        except ValueError:
            pass
    return _CUSTOM_SOUND_AUDIO_MAX_HOURS


# 등록 음원 원본 파일 TTL (시간). 만료 후 파일 삭제·DB audio_path 비움. 임베딩은 유지.
CUSTOM_SOUND_AUDIO_RETENTION_HOURS = _custom_sound_audio_retention_hours()
