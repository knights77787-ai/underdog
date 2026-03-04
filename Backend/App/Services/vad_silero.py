"""
Silero VAD 스트리밍 래퍼.
세션별로 VADIterator를 하나씩 가지고, audio_chunk(float32)을 넣으면
speech start/end 이벤트(dict)를 뱉어주는 스트리밍 VAD.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

import numpy as np
import torch

from silero_vad import VADIterator, load_silero_vad


@dataclass
class VADConfig:
    """VAD 파라미터."""
    sr: int = 16000
    threshold: float = 0.5  # speech prob threshold
    min_silence_ms: int = 300  # silence to close segment
    speech_pad_ms: int = 30  # pad around speech


class SileroVADStream:
    """세션별 VADIterator 보유, feed 시 start/end 이벤트 반환."""

    def __init__(self, cfg: VADConfig | None = None):
        self.cfg = cfg or VADConfig()
        self.device = torch.device("cpu")
        self.model = load_silero_vad().to(self.device)

    def new_iterator(self) -> VADIterator:
        """세션당 하나씩 생성해 사용."""
        return VADIterator(
            self.model,
            threshold=self.cfg.threshold,
            sampling_rate=self.cfg.sr,
            min_silence_duration_ms=self.cfg.min_silence_ms,
            speech_pad_ms=self.cfg.speech_pad_ms,
        )

    def feed(
        self,
        it: VADIterator,
        audio_f32: np.ndarray,
    ) -> Optional[Dict[str, Any]]:
        """audio_f32: float32 mono, 16kHz, shape (N,). None 또는 {"start": idx} / {"end": idx} 등."""
        if audio_f32.size == 0:
            return None
        x = torch.from_numpy(audio_f32).to(self.device)  # (N,) float32
        return it(x)
