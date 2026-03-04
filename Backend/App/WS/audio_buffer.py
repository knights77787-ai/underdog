"""
오디오 청크 디코딩 및 세션별 버퍼 관리.

- base64 PCM S16LE 디코딩 → int16 → float32
- 세션별 롤링 버퍼(max_seconds), VAD 상태·speech_buf 보관
"""
import base64
from dataclasses import dataclass, field
from typing import Dict, List

import numpy as np


def decode_pcm16_b64(data_b64: str) -> np.ndarray:
    """base64 문자열(PCM raw bytes)을 int16 넘파이 배열로 디코딩."""
    raw = base64.b64decode(data_b64)
    audio_i16 = np.frombuffer(raw, dtype=np.int16)
    return audio_i16


def i16_to_f32(audio_i16: np.ndarray) -> np.ndarray:
    """int16 배열을 [-1, 1] 범위 float32로 변환."""
    return audio_i16.astype(np.float32) / 32768.0


@dataclass
class AudioSessionBuffer:
    """세션 하나당 오디오 버퍼 + VAD 상태."""
    sr: int = 16000
    buf: np.ndarray = field(default_factory=lambda: np.zeros((0,), dtype=np.float32))
    in_speech: bool = False
    speech_buf: List[np.ndarray] = field(default_factory=list)
    last_ts_ms: int | None = None


class AudioBufferStore:
    """세션별 AudioSessionBuffer 관리. 롤링 버퍼(max_samples) 유지."""

    def __init__(self, max_seconds: float = 10.0, sr: int = 16000):
        self.sr = sr
        self.max_samples = int(max_seconds * sr)
        self.sessions: Dict[str, AudioSessionBuffer] = {}

    def get(self, session_id: str) -> AudioSessionBuffer:
        if session_id not in self.sessions:
            self.sessions[session_id] = AudioSessionBuffer(sr=self.sr)
        return self.sessions[session_id]

    def append(
        self,
        session_id: str,
        audio_f32: np.ndarray,
        ts_ms: int | None = None,
    ) -> AudioSessionBuffer:
        s = self.get(session_id)
        s.last_ts_ms = ts_ms
        s.buf = np.concatenate([s.buf, audio_f32])
        # keep last max samples
        if s.buf.shape[0] > self.max_samples:
            s.buf = s.buf[-self.max_samples:]
        return s
