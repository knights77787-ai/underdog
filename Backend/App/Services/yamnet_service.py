# app/Services/yamnet_service.py
import csv
from pathlib import Path

import numpy as np
import tensorflow as tf
import tensorflow_hub as hub

from app.Core.config import YAMNET_CLASS_MAP_PATH


def _load_class_map(path: Path) -> dict[int, str]:
    """CSV에서 index -> display_name 매핑 로드."""
    if not path.exists():
        return {}
    out: dict[int, str] = {}
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f, skipinitialspace=True)
        for row in reader:
            try:
                idx = int(row["index"])
                name = row.get("display_name") or row.get("display_name ") or ""
                out[idx] = name.strip()
            except (ValueError, KeyError):
                pass
    return out


class YamnetService:
    def __init__(self, model_url: str = "https://tfhub.dev/google/yamnet/1"):
        self.model = hub.load(model_url)
        self.index_to_label = _load_class_map(YAMNET_CLASS_MAP_PATH)

    def predict_index(self, waveform_16k_f32: np.ndarray) -> tuple[int, float]:
        """
        waveform_16k_f32: float32 mono 16kHz (N,)
        returns: (top_index, top_score)
        """
        top_i, top_score, _ = self.predict(waveform_16k_f32)
        return top_i, top_score

    def predict(self, waveform_16k_f32: np.ndarray) -> tuple[int, float, str]:
        """
        waveform_16k_f32: float32 mono 16kHz (N,)
        returns: (top_index, top_score, label)
        """
        x = tf.convert_to_tensor(waveform_16k_f32, dtype=tf.float32)
        scores, _, _ = self.model(x)
        mean_scores = tf.reduce_mean(scores, axis=0).numpy()
        top_i = int(np.argmax(mean_scores))
        top_score = float(mean_scores[top_i])
        label = self.index_to_label.get(top_i, str(top_i))
        return top_i, top_score, label

    def embedding_1s(self, waveform_16k_f32: np.ndarray) -> np.ndarray:
        """
        1초(16000 samples) 권장.
        return: (1024,) float32 YAMNet embedding (정규화 벡터).
        """
        x = tf.convert_to_tensor(waveform_16k_f32, dtype=tf.float32)
        _, embeddings, _ = self.model(x)
        emb = tf.reduce_mean(embeddings, axis=0).numpy().astype(np.float32)
        n = np.linalg.norm(emb) + 1e-9
        return emb / n

