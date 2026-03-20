"""
Whisper STT via OpenAI Whisper API (API 키 사용).
로컬 모델 대신 API 호출 → 서버 메모리 절감. OPENAI_API_KEY 설정 시 사용.
"""
from __future__ import annotations

import io
import os
import re
import wave

import numpy as np
import httpx

from App.Core.logging import get_logger

logger = get_logger("stt.whisper_api")

# STT 언어 (한글)
STT_LANGUAGE = "ko"
OPENAI_TRANSCRIPTIONS_URL = "https://api.openai.com/v1/audio/transcriptions"

# 학습 데이터에 흔한 불필요 문장 필터 (할루시네이션 감소)
BANNED_TOKENS = frozenset({
    "네",
    "네 그렇습니다",
    "감사합니다",
    "고맙습니다",
    "시청해주셔서 감사합니다",
    "구독과 좋아요",
    "한국어",
    "한국어로 말합니다",
    "한국어로 말합니다.",
})


def sanitize_whisper_transcript(text: str) -> str:
    """
    Whisper가 잡음에서 프롬프트/메타 단어를 반복 출력하는 경우 제거.
    특히 prompt에 '한국어'가 있으면 '방송, 한국어, 한국어, ...' 식 출력이 자주 난다.
    """
    if not text or not str(text).strip():
        return ""
    t = str(text).strip()
    n_ko = len(re.findall(r"\b한국어\b", t))
    if n_ko == 0:
        return t

    parts = [p for p in re.split(r"[\s,，、]+", t) if p]
    if not parts:
        return ""

    if len(parts) == 1 and parts[0] == "한국어":
        return ""

    if n_ko >= 3 and (n_ko / len(parts)) >= 0.35:
        logger.info(
            "WHISPER_SANITIZE drop reason=korean_meta_spam n_ko=%s parts=%s sample=%r",
            n_ko,
            len(parts),
            t[:80],
        )
        return ""

    if all(p == "한국어" for p in parts):
        return ""

    if len(t) > 50 and n_ko >= 4:
        logger.info("WHISPER_SANITIZE drop reason=korean_repeat_long text_len=%s n_ko=%s", len(t), n_ko)
        return ""

    low = t.lower()
    if low in ("korean", "korean language"):
        return ""
    return t


def _float32_16k_to_wav_bytes(audio: np.ndarray) -> bytes:
    """float32 mono 16kHz [-1, 1] → 16bit PCM WAV bytes."""
    audio = np.asarray(audio, dtype=np.float32).ravel()
    audio = np.clip(audio, -1.0, 1.0)
    # float -> int16
    pcm = (audio * 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(pcm.tobytes())
    return buf.getvalue()


class WhisperAPISTT:
    """
    OpenAI Whisper API로 음성→텍스트 변환.
    """

    def __init__(self, api_key: str | None = None, model: str = "whisper-1"):
        self.api_key = (api_key or os.environ.get("OPENAI_API_KEY") or "").strip()
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is required for WhisperAPISTT")
        self.model = model

    def transcribe_16k_f32(
        self,
        audio_f32_16k: np.ndarray,
        initial_prompt: str | None = None,
    ) -> str:
        """audio_f32_16k: float32 mono 16kHz. initial_prompt로 도메인/어휘 힌트 전달."""
        if audio_f32_16k is None:
            return ""
        audio = np.asarray(audio_f32_16k, dtype=np.float32)
        if audio.ndim == 2:
            if audio.shape[0] == 1 or audio.shape[1] == 1:
                audio = audio.reshape(-1)
            else:
                audio = audio.mean(axis=1)
        audio = np.ravel(audio)
        audio = np.nan_to_num(audio, nan=0.0, posinf=0.0, neginf=0.0)
        audio = np.clip(audio, -1.0, 1.0)
        audio = audio - np.mean(audio)
        peak = float(np.max(np.abs(audio)))
        if peak > 0.01:
            audio = (audio * (0.95 / peak)).astype(np.float32)
        if audio.shape[0] < 16000 * 0.5:
            return ""
        logger.info(
            "WHISPER_API INPUT shape=%s dtype=%s",
            audio.shape,
            audio.dtype,
        )
        wav_bytes = _float32_16k_to_wav_bytes(audio)
        raw_prompt = (initial_prompt or "").strip()
        # 사용자/기본값 모두: 프롬프트에 '한국어' 넣으면 Whisper가 잡음에서 해당 단어를 반복 출력하기 쉬움
        if raw_prompt:
            prompt = re.sub(r"\b한국어\b", " ", raw_prompt)
            prompt = re.sub(r"\s*,\s*,", ",", prompt)
            prompt = re.sub(r"\s+", " ", prompt).strip(" ,")
        else:
            prompt = ""
        if not prompt:
            prompt = "안전 안내, 화재 대피, 일상 대화, 열차 문 닫힘"
        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(
                    OPENAI_TRANSCRIPTIONS_URL,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    files={"file": ("audio.wav", wav_bytes, "audio/wav")},
                    data={
                        "model": self.model,
                        "language": STT_LANGUAGE,
                        **({"prompt": prompt} if prompt else {}),
                        "response_format": "json",
                        "temperature": 0.2,  # 낮을수록 일관·할루시네이션 감소
                    },
                )
            resp.raise_for_status()
            data = resp.json()
            text = (data.get("text") or "").strip()
        except httpx.HTTPStatusError as e:
            logger.exception("WHISPER_API HTTP error %s: %s", e.response.status_code, e.response.text)
            return ""
        except Exception:
            logger.exception("WHISPER_API request failed")
            return ""
        if not text:
            return ""
        text = sanitize_whisper_transcript(text)
        if not text:
            return ""
        # 끝 마침표/공백 제거 후 금지 문구 매칭 (예: "시청해주셔서 감사합니다." → 필터)
        text_normalized = text.rstrip(".!? \t\n\r")
        if text_normalized in BANNED_TOKENS:
            return ""
        if text == "한국어로 말합니다." or (prompt and text == prompt.strip()):
            return ""
        text_no_space = text.replace(" ", "")
        if len(text_no_space) >= 6 and len(set(text_no_space)) <= 3:
            return ""
        return text
