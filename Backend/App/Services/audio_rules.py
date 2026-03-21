# App/Services/audio_rules.py
import csv
import json
from pathlib import Path
from threading import RLock

from App.Core.config import EVENT_TYPES_PATH, YAMNET_CLASS_MAP_PATH

_LOCK = RLock()

_audio_min_score = 0.35
_warning_labels: set[str] = set()
_caution_labels: set[str] = set()
_daily_labels: set[str] = set()
_warning_indices: set[int] = set()
_caution_indices: set[int] = set()
_daily_indices: set[int] = set()
_yamnet_label_to_subgroup: dict[str, str] = {}
# 비언어 알림에서 제외(말소리·숨·군중 말잡음·침묵 등). CSV display_name과 일치해야 함.
_yamnet_skip_alert_labels: set[str] = set()

def reload_audio_rules() -> dict:
    global _audio_min_score, _warning_labels, _caution_labels, _daily_labels
    global _warning_indices, _caution_indices, _daily_indices
    global _yamnet_label_to_subgroup
    global _yamnet_skip_alert_labels

    if not EVENT_TYPES_PATH.exists():
        with _LOCK:
            _audio_min_score = 0.35
            _warning_labels = set()
            _caution_labels = set()
            _daily_labels = set()
            _warning_indices = set()
            _caution_indices = set()
            _daily_indices = set()
            _yamnet_label_to_subgroup = {}
            _yamnet_skip_alert_labels = set()
        return {"ok": False, "reason": "EVENT_TYPES_PATH missing", "path": str(EVENT_TYPES_PATH)}

    data = json.loads(EVENT_TYPES_PATH.read_text(encoding="utf-8"))
    audio_rules = data.get("audio_rules", {}) or {}

    min_score = float(audio_rules.get("min_score", 0.35))

    w_labels = [s.strip() for s in (audio_rules.get("warning_labels") or []) if s and isinstance(s, str)]
    c_labels = [s.strip() for s in (audio_rules.get("caution_labels") or []) if s and isinstance(s, str)]
    d_labels = [s.strip() for s in (audio_rules.get("daily_labels") or []) if s and isinstance(s, str)]
    w_idx = audio_rules.get("warning_indices", []) or []
    c_idx = audio_rules.get("caution_indices", []) or []
    d_idx = audio_rules.get("daily_indices", []) or []
    raw_sub_map = audio_rules.get("yamnet_label_to_subgroup") or {}
    label_to_sub: dict[str, str] = {}
    if isinstance(raw_sub_map, dict):
        for k, v in raw_sub_map.items():
            if isinstance(k, str) and isinstance(v, str) and k.strip() and v.strip():
                label_to_sub[k.strip()] = v.strip()

    skip_raw = audio_rules.get("yamnet_skip_alert_labels") or []
    skip_labels: set[str] = set()
    if isinstance(skip_raw, list):
        for s in skip_raw:
            if isinstance(s, str) and s.strip():
                skip_labels.add(s.strip())

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
        _caution_labels = set(c_labels)
        _daily_labels = set(d_labels)
        _warning_indices = to_int_set(w_idx)
        _caution_indices = to_int_set(c_idx)
        _daily_indices = to_int_set(d_idx)
        _yamnet_label_to_subgroup = label_to_sub
        _yamnet_skip_alert_labels = skip_labels

    return {
        "ok": True,
        "path": str(EVENT_TYPES_PATH),
        "min_score": _audio_min_score,
        "warning_count": len(_warning_labels) or len(_warning_indices),
        "caution_count": len(_caution_labels) or len(_caution_indices),
        "daily_count": len(_daily_labels) or len(_daily_indices),
        "yamnet_skip_alert_count": len(skip_labels),
    }

def classify_audio(
    top_index: int, score: float, label: str = ""
) -> tuple[str | None, str | None]:
    """
    return: (event_type, keyword)
    event_type: "danger" | "caution" | "alert" | None (Warning|Caution|Daily)
    """
    with _LOCK:
        min_score = _audio_min_score
        w_lab = _warning_labels
        c_lab = _caution_labels
        d_lab = _daily_labels
        w_idx = _warning_indices
        c_idx = _caution_indices
        d_idx = _daily_indices

    if score < min_score:
        return None, None

    lab = (label or "").strip()
    with _LOCK:
        skip_lab = _yamnet_skip_alert_labels
    if lab and lab in skip_lab:
        return None, None

    use_labels = bool(w_lab or c_lab or d_lab)
    if use_labels and lab:
        if lab in w_lab:
            return "danger", lab
        if lab in c_lab:
            return "caution", lab
        if lab in d_lab:
            return "alert", lab
    else:
        if top_index in w_idx:
            return "danger", str(top_index)
        if top_index in c_idx:
            return "caution", str(top_index)
        if top_index in d_idx:
            return "alert", str(top_index)

    return None, None


def get_audio_min_score() -> float:
    """YAMNet classify_audio 에 쓰는 min_score (설정 동기화용)."""
    with _LOCK:
        return float(_audio_min_score)


def yamnet_subgroup_for_label(label: str) -> str | None:
    """YAMNet display label → keywords_by_event_type 하위그룹 키(열차 등). 없으면 None."""
    if not label or not isinstance(label, str):
        return None
    with _LOCK:
        return _yamnet_label_to_subgroup.get(label.strip())


def get_audio_rules_status() -> dict:
    with _LOCK:
        return {
            "min_score": _audio_min_score,
            "warning_count": len(_warning_labels) or len(_warning_indices),
            "caution_count": len(_caution_labels) or len(_caution_indices),
            "daily_count": len(_daily_labels) or len(_daily_indices),
            "yamnet_skip_alert_count": len(_yamnet_skip_alert_labels),
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


reload_audio_rules()