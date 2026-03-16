"""
세션별 VAD 상태 저장: VADIterator + speech 수집 버퍼.
AudioBufferStore와 별도로, VAD 이터레이터와 speech_chunks만 관리.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np

from silero_vad import VADIterator


@dataclass
class AudioState:
    """세션당 VAD 이터레이터 + speech 수집 버퍼 + 커스텀 소리 윈도우용 버퍼."""
    vad_it: VADIterator
    in_speech: bool = False
    speech_chunks: List[np.ndarray] = field(default_factory=list)
    # 커스텀 소리 매칭용: VAD와 무관하게 항상 수집 (박수·초인종 등 짧은 소리도 감지)
    custom_sound_chunks: List[np.ndarray] = field(default_factory=list)


class AudioStateStore:
    """session_id → AudioState 저장/조회/삭제."""

    def __init__(self) -> None:
        self.states: Dict[str, AudioState] = {}

    def get(self, session_id: str) -> Optional[AudioState]:
        return self.states.get(session_id)

    def set(self, session_id: str, st: AudioState) -> None:
        self.states[session_id] = st

    def remove(self, session_id: str) -> None:
        self.states.pop(session_id, None)
