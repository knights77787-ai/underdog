"""
Whisper STT: 모델 1회 로드 + numpy(float32 16kHz) 입력으로 변환.
튜닝: 환각 많으면 no_speech_threshold 0.6~0.8·RMS 스킵 임계 올리기.
      인식이 너무 비어 있으면 no_speech_threshold 0.4~0.6으로 낮추기.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import whisper


@dataclass
class WhisperConfig:
    """Whisper 설정. tiny/base/small 등, MVP는 base 권장."""
    model_name: str = "base"
    language: str | None = "ko"  # "ko" 추천, None이면 자동 감지


class WhisperSTT:
    """모델 1회 로드 후 transcribe_16k_f32로 변환."""

    def __init__(self, cfg: WhisperConfig | None = None):
        self.cfg = cfg or WhisperConfig()
        self.model = whisper.load_model(self.cfg.model_name)  # load once

    def transcribe_16k_f32(self, audio_f32_16k: np.ndarray) -> str:
        """audio_f32_16k: float32 mono 16kHz, range -1~1, shape (N,)"""
        if audio_f32_16k is None or audio_f32_16k.size == 0:
            return ""
        # whisper가 기대하는 형태로 보정
        audio = audio_f32_16k.astype(np.float32)
        # 너무 짧으면(예: 0.2초 이하) 빈값 처리
        if audio.shape[0] < 16000 * 0.2:
            return ""
        # Whisper는 내부적으로 30초 단위로 pad/trim함. 환각↓/한국어 안정 우선 옵션.
        result = self.model.transcribe(
            audio,
            language=self.cfg.language,
            task="transcribe",
            fp16=False,
            temperature=0.0,
            beam_size=1,
            best_of=1,
            no_speech_threshold=0.6,
            logprob_threshold=-1.0,
            compression_ratio_threshold=2.4,
            condition_on_previous_text=False,
            verbose=False,
        )
        text = (result.get("text") or "").strip()
        return text
