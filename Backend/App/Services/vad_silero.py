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
        """audio_f32: float32 mono, 16kHz, shape (N,).

        Silero VADIterator는 16kHz에서 한 번에 512 샘플만 허용한다.
        프론트엔드에서는 0.5초(8000샘플) 단위로 audio_chunk를 보내므로,
        여기에서 512 샘플 단위로 잘라서 iterator에 순차적으로 먹이고
        마지막으로 발생한 이벤트(있다면)를 반환한다.
        """
        if audio_f32.size == 0:
            return None

        num_samples = 512 if self.cfg.sr == 16000 else 256
        last_ev: Optional[Dict[str, Any]] = None

        for start in range(0, audio_f32.shape[0], num_samples):
            chunk = audio_f32[start : start + num_samples]
            if chunk.shape[0] < num_samples:
                # Silero는 고정 길이를 요구하므로 0으로 패딩
                pad = np.zeros(num_samples, dtype=np.float32)
                pad[: chunk.shape[0]] = chunk
                chunk = pad

            x = torch.from_numpy(chunk).to(self.device)  # (num_samples,) float32
            ev = it(x)
            if ev is not None:
                last_ev = ev

        return last_ev
