from __future__ import annotations

import numpy as np


def emb_to_blob(emb: np.ndarray) -> tuple[bytes, int]:
    """float32 embedding -> (blob, dim)."""
    emb = emb.astype(np.float32)
    return emb.tobytes(), emb.shape[0]


def blob_to_emb(blob: bytes, dim: int) -> np.ndarray:
    """(blob, dim) -> float32 embedding."""
    return np.frombuffer(blob, dtype=np.float32, count=dim)
