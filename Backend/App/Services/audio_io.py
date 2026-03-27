from __future__ import annotations

import io

import numpy as np
from fastapi import HTTPException
from scipy.signal import resample


def resample_to_16k(x: np.ndarray, sr: int) -> np.ndarray:
    if sr == 16000:
        return x.astype(np.float32)
    if sr <= 0:
        raise ValueError("invalid sample rate")
    new_len = int(round(len(x) * 16000 / sr))
    if new_len <= 0:
        raise ValueError("invalid resample length")
    y = resample(x, new_len)
    return y.astype(np.float32)


def decode_wav_to_16k_mono_f32(wav_bytes: bytes) -> np.ndarray:
    # TensorFlow decode는 wav 헤더/채널 처리 호환성이 좋아 유지
    import tensorflow as tf

    audio, sr = tf.audio.decode_wav(wav_bytes)  # (samples, channels) float32 -1..1
    audio = tf.reduce_mean(audio, axis=1)
    sr = int(sr.numpy())
    x = audio.numpy().astype(np.float32)
    return resample_to_16k(x, sr)


def decode_via_pydub(data: bytes, fmt: str) -> np.ndarray:
    try:
        from pydub import AudioSegment
    except ImportError:
        raise HTTPException(
            503,
            "오디오 디코딩을 위해 pydub가 필요합니다. pip install pydub 및 ffmpeg 설치 후 이용하세요.",
        )
    try:
        seg = AudioSegment.from_file(io.BytesIO(data), format=fmt)
    except Exception as e:
        raise HTTPException(400, f"{fmt.upper()} 디코딩 실패. ffmpeg 설치 여부를 확인하세요: {e!s}")
    seg = seg.set_channels(1)
    sr = seg.frame_rate
    samples = np.array(seg.get_array_of_samples(), dtype=np.float32) / 32768.0
    return resample_to_16k(samples, sr)


def decode_audio_to_16k_mono_f32(
    data: bytes,
    ext: str,
    *,
    allowed_extensions: tuple[str, ...],
) -> np.ndarray:
    ext = ext.lower()
    if ext == ".wav":
        return decode_wav_to_16k_mono_f32(data)
    if ext == ".mp3":
        return decode_via_pydub(data, "mp3")
    if ext == ".weba":
        return decode_via_pydub(data, "webm")
    if ext == ".m4a":
        return decode_via_pydub(data, "m4a")
    if ext == ".ogg":
        return decode_via_pydub(data, "ogg")
    raise HTTPException(400, f"지원하지 않는 형식입니다. 사용 가능: {', '.join(allowed_extensions)}")
