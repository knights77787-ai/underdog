"""
Whisper STT: 모델 1회 로드 + numpy(float32 16kHz) 입력으로 변환.
튜닝: 환각 많으면 no_speech_threshold 0.6~0.8·RMS 스킵 임계 올리기.
      인식이 너무 비어 있으면 no_speech_threshold 0.4~0.6으로 낮추기.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import whisper

from App.Core.logging import get_logger

logger = get_logger("stt.whisper")


@dataclass
class WhisperConfig:
    """Whisper 설정. tiny/base/small 등, MVP는 base 권장."""
    model_name: str = "base"
    language: str | None = "ko"  # "ko" 추천, None이면 자동 감지
    beam_size: int = 4  # 기본값; 호출 시 인자로 오면 그걸 사용(세션 설정 연동)


class WhisperSTT:
    """모델 1회 로드 후 transcribe_16k_f32로 변환."""

    def __init__(self, cfg: WhisperConfig | None = None):
        self.cfg = cfg or WhisperConfig()
        self.model = whisper.load_model(self.cfg.model_name)  # load once

    def transcribe_16k_f32(
        self,
        audio_f32_16k: np.ndarray,
        beam_size: int | None = None,
    ) -> str:
        """audio_f32_16k: float32 mono 16kHz, range -1~1, shape (N,) or (C,N). beam_size None이면 cfg 값 사용."""
        if audio_f32_16k is None:
            return ""
        audio = np.asarray(audio_f32_16k, dtype=np.float32)
        if audio.ndim == 2:
            if audio.shape[0] == 1 or audio.shape[1] == 1:
                audio = audio.reshape(-1)
            else:
                audio = audio.mean(axis=1)
        audio = np.ravel(audio)
        audio = np.ascontiguousarray(audio, dtype=np.float32)
        if audio.size == 0:
            return ""
        audio = np.nan_to_num(audio, nan=0.0, posinf=0.0, neginf=0.0)
        audio = np.clip(audio, -1.0, 1.0)
        # 입력 오디오 품질: DC 제거, 피크 정규화 (인식 안정성·정확도 보조)
        audio = audio - np.mean(audio)
        peak = float(np.max(np.abs(audio)))
        if peak > 0.01:
            audio = (audio * (0.95 / peak)).astype(np.float32)
        audio = np.clip(audio, -1.0, 1.0)
        # 최소 0.5초~1초 권장
        if audio.shape[0] < 16000 * 0.5:
            return ""
        logger.info(
            "WHISPER INPUT shape=%s dtype=%s min=%.4f max=%.4f",
            audio.shape,
            audio.dtype,
            float(audio.min()) if audio.size else 0.0,
            float(audio.max()) if audio.size else 0.0,
        )
        beam = beam_size if beam_size is not None else self.cfg.beam_size
        result = self.model.transcribe(
            audio,
            language=self.cfg.language,
            task="transcribe",
            fp16=False,
            temperature=0.0,
            beam_size=beam,
            best_of=1,
            no_speech_threshold=0.6,
            logprob_threshold=-1.0,
            compression_ratio_threshold=2.4,
            condition_on_previous_text=False,
            verbose=False,
        )
        return (result.get("text") or "").strip()
