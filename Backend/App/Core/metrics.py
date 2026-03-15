# App/Core/metrics.py
from dataclasses import dataclass
from threading import Lock

@dataclass
class QueueMetrics:
    stt_enqueued: int = 0
    stt_dropped: int = 0
    stt_processed: int = 0
    stt_time_sum_ms: int = 0
    stt_time_max_ms: int = 0

    yamnet_enqueued: int = 0
    yamnet_dropped: int = 0
    yamnet_processed: int = 0
    yamnet_time_sum_ms: int = 0
    yamnet_time_max_ms: int = 0

_lock = Lock()
_metrics = QueueMetrics()

def inc(name: str, n: int = 1):
    with _lock:
        setattr(_metrics, name, getattr(_metrics, name) + n)

def add_time(model: str, dt_ms: int):
    """처리 시간(ms) 누적. model: 'stt' | 'yamnet'."""
    with _lock:
        if model == "stt":
            _metrics.stt_time_sum_ms += dt_ms
            if dt_ms > _metrics.stt_time_max_ms:
                _metrics.stt_time_max_ms = dt_ms
        elif model == "yamnet":
            _metrics.yamnet_time_sum_ms += dt_ms
            if dt_ms > _metrics.yamnet_time_max_ms:
                _metrics.yamnet_time_max_ms = dt_ms

def snapshot() -> dict:
    with _lock:
        return _metrics.__dict__.copy()

def derived() -> dict:
    """snapshot + stt_avg_ms, yamnet_avg_ms (발표용 성능)."""
    s = snapshot()
    stt_avg = (s["stt_time_sum_ms"] / s["stt_processed"]) if s["stt_processed"] else 0
    yamnet_avg = (s["yamnet_time_sum_ms"] / s["yamnet_processed"]) if s["yamnet_processed"] else 0
    s["stt_avg_ms"] = round(stt_avg, 1)
    s["yamnet_avg_ms"] = round(yamnet_avg, 1)
    return s