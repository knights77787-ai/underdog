"""Whisper encoder embedding 추출 유틸."""

from __future__ import annotations

import numpy as np
import whisper


class WhisperEmbedder:
    def __init__(self, model_name: str = "base"):
        self.model = whisper.load_model(model_name)

    def embed_16k_f32(self, audio_f32_16k: np.ndarray) -> np.ndarray:
        """
        audio_f32_16k: float32 mono 16kHz (-1..1), shape (N,)
        return: (D,) float32 normalized embedding.
        """
        audio = audio_f32_16k.astype(np.float32)

        # Whisper 입력용 mel 생성
        mel = whisper.log_mel_spectrogram(audio)
        mel = mel.to(self.model.device)

        with np.errstate(all="ignore"):
            enc = self.model.encoder(mel.unsqueeze(0))  # (1, T, D)

        emb = enc[0].mean(dim=0).detach().cpu().numpy().astype(np.float32)  # (D,)
        emb /= (np.linalg.norm(emb) + 1e-9)
        return emb


# 공유 인스턴스 (라우트·매칭에서 한 번만 로드)
PHRASE_EMB = WhisperEmbedder("base")

