# App/Services/audio_rules.py
import csv
import json
from pathlib import Path
from threading import RLock

from App.Core.config import EVENT_TYPES_PATH, YAMNET_CLASS_MAP_PATH

_LOCK = RLock()

_audio_min_score = 0.35
_warning_labels: set[str] = set()
_daily_labels: set[str] = set()
# 하위 호환: index 기반 설정만 있으면 계속 사용
_warning_indices: set[int] = set()
_daily_indices: set[int] = set()

def reload_audio_rules() -> dict:
    global _audio_min_score, _warning_labels, _daily_labels, _warning_indices, _daily_indices

    if not EVENT_TYPES_PATH.exists():
        with _LOCK:
            _audio_min_score = 0.35
            _warning_labels = set()
            _daily_labels = set()
            _warning_indices = set()
            _daily_indices = set()
        return {"ok": False, "reason": "EVENT_TYPES_PATH missing", "path": str(EVENT_TYPES_PATH)}

    data = json.loads(EVENT_TYPES_PATH.read_text(encoding="utf-8"))
    audio_rules = data.get("audio_rules", {}) or {}

    min_score = float(audio_rules.get("min_score", 0.35))

    # label 기반 (운영/발표용 권장)
    w_labels = [s.strip() for s in (audio_rules.get("warning_labels") or []) if s and isinstance(s, str)]
    d_labels = [s.strip() for s in (audio_rules.get("daily_labels") or []) if s and isinstance(s, str)]
    # 하위 호환: index 기반
    w_idx = audio_rules.get("warning_indices", []) or []
    d_idx = audio_rules.get("daily_indices", []) or []

    def to_int_set(xs):
        out = set()
        for x in xs:
            try:
                out.add(int(x))
            except Exception:
                pass
        return out

    with _LOCK:
        _audio_min_score = min_score
        _warning_labels = set(w_labels)
        _daily_labels = set(d_labels)
        _warning_indices = to_int_set(w_idx)
        _daily_indices = to_int_set(d_idx)

    return {
        "ok": True,
        "path": str(EVENT_TYPES_PATH),
        "min_score": _audio_min_score,
        "warning_count": len(_warning_labels) or len(_warning_indices),
        "daily_count": len(_daily_labels) or len(_daily_indices),
    }

def classify_audio(
    top_index: int, score: float, label: str = ""
) -> tuple[str | None, str | None]:
    """
    return: (event_type, keyword)
    event_type: "danger" | "alert" | None
    keyword: label 문자열(라벨 기반) 또는 index 문자열(인덱스 기반)
    label 기반: warning_labels/daily_labels 있으면 top_label로 매칭.
    """
    with _LOCK:
        min_score = _audio_min_score
        w_lab = _warning_labels
        d_lab = _daily_labels
        w_idx = _warning_indices
        d_idx = _daily_indices

    if score < min_score:
        return None, None

    use_labels = bool(w_lab or d_lab)
    if use_labels and label:
        if label in w_lab:
            return "danger", label
        if label in d_lab:
            return "alert", label
    else:
        if top_index in w_idx:
            return "danger", str(top_index)
        if top_index in d_idx:
            return "alert", str(top_index)

    return None, None

def get_audio_rules_status() -> dict:
    with _LOCK:
        return {
            "min_score": _audio_min_score,
            "warning_count": len(_warning_labels) or len(_warning_indices),
            "daily_count": len(_daily_labels) or len(_daily_indices),
        }


# YAMNet class map (index → display_name). Backend/App/resources/yamnet_class_map.csv
_yamnet_display_names: dict[int, str] = {}


def _load_yamnet_class_map() -> None:
    global _yamnet_display_names
    if not YAMNET_CLASS_MAP_PATH.exists():
        _yamnet_display_names = {}
        return
    with _LOCK:
        _yamnet_display_names = {}
        with open(YAMNET_CLASS_MAP_PATH, encoding="utf-8") as f:
            for row in csv.DictReader(f, skipinitialspace=True):
                try:
                    idx = int(row["index"])
                    name = row.get("display_name") or row.get("display_name ") or ""
                    _yamnet_display_names[idx] = name.strip()
                except (ValueError, KeyError):
                    pass


def get_yamnet_display_name(index: int) -> str:
    """YAMNet index → display_name. CSV 없으면 index 문자열 반환."""
    if not _yamnet_display_names and YAMNET_CLASS_MAP_PATH.exists():
        _load_yamnet_class_map()
    return _yamnet_display_names.get(index, str(index))