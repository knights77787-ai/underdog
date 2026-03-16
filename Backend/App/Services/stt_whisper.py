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

# STT 언어 고정 (한글)
STT_LANGUAGE = "ko"
# initial_prompt: 비우면 프롬프트가 그대로 자막으로 나오는 현상 방지 (필요 시 세션 설정에서 짧은 힌트만)
STT_INITIAL_PROMPT = ""
# best_of: 0 또는 1=가장 빠름(1회 디코딩), 2~3=정확하지만 지연 증가
STT_BEST_OF = 0
# no_speech_threshold: 높을수록 말 없는 구간을 빈 결과로 (환각·노이즈 감소). 0.7 완화 권장.
NO_SPEECH_THRESHOLD = 0.7
# 환각 구간 앞 무음 스킵 (초). 짧은 발화/작은 음량 보존에 유리.
HALLUCINATION_SILENCE_THRESHOLD = 2.0

# 학습 데이터에 흔한 불필요 문장 필터 (할루시네이션 감소)
BANNED_TOKENS = frozenset({
    "네",
    "네 그렇습니다",
    "감사합니다",
    "고맙습니다",
    "시청해주셔서 감사합니다",
    "구독과 좋아요",
})


@dataclass
class WhisperConfig:
    """Whisper 설정. tiny/base/small 등, MVP는 base 권장. 언어는 STT_LANGUAGE로 한글 고정."""
    model_name: str = "base"
    language: str = "ko"  # 한글 고정 (실제 transcribe는 STT_LANGUAGE 사용)
    beam_size: int = 2  # 1=가장 빠름, 2=속도·정확 균형, 3~5=정확하지만 느려짐


class WhisperSTT:
    """모델 1회 로드 후 transcribe_16k_f32로 변환."""

    def __init__(self, cfg: WhisperConfig | None = None):
        self.cfg = cfg or WhisperConfig()
        self.model = whisper.load_model(self.cfg.model_name)  # load once

    def transcribe_16k_f32(
        self,
        audio_f32_16k: np.ndarray,
        beam_size: int | None = None,
        initial_prompt: str | None = None,
        best_of: int | None = None,
    ) -> str:
        """audio_f32_16k: float32 mono 16kHz, range -1~1. None인 인자는 모듈 기본값 사용(세션 설정 연동)."""
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
        # 최소 0.5초 (청크 0.5~3초 범위 지원)
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
        prompt = initial_prompt if initial_prompt is not None else STT_INITIAL_PROMPT
        n_best = best_of if best_of is not None else STT_BEST_OF
        # Whisper는 best_of 최소 1 (0이면 1로 처리해 가장 빠르게)
        n_best = max(1, int(n_best)) if n_best is not None else 1
        result = self.model.transcribe(
            audio,
            language=STT_LANGUAGE,
            task="transcribe",
            fp16=False,
            temperature=0.0,
            beam_size=beam,
            best_of=n_best,
            no_speech_threshold=NO_SPEECH_THRESHOLD,
            logprob_threshold=-1.0,
            compression_ratio_threshold=2.4,
            condition_on_previous_text=False,
            initial_prompt=prompt if prompt else None,
            verbose=False,
            hallucination_silence_threshold=HALLUCINATION_SILENCE_THRESHOLD,
        )
        text = (result.get("text") or "").strip()
        # 프롬프트가 그대로 나오거나 환각(반복 문자)이면 빈 결과로
        if not text:
            return ""
        # 끝 마침표/공백 제거 후 금지 문구 매칭 (예: "시청해주셔서 감사합니다." → 필터)
        text_normalized = text.rstrip(".!? \t\n\r")
        if text_normalized in BANNED_TOKENS:
            return ""
        if text == "한국어로 말합니다." or (prompt and text == prompt.strip()):
            return ""
        # ㅎㅎㅎ, 흐흐흐, ◆◇ 반복 등 환각 패턴: 고유 문자 수가 극소이고 길면 스킵
        text_no_space = text.replace(" ", "")
        if len(text_no_space) >= 6 and len(set(text_no_space)) <= 3:
            return ""
        return text
