# App/WS/audio_cls_worker.py
# db 세션은 worker에 넘기지 말고, settings는 handlers에서 미리 읽어 item에 값만 넘김.
# 커스텀 사운드: 실시간 오디오 embedding → DB 저장 커스텀 소리와 유사도 비교 → Event-builder(alert/로그) 통합.
import asyncio
import os
import time
import numpy as np

from App.Core.logging import get_logger
from App.Core.metrics import add_time, inc
from App.Services.audio_rules import (
    classify_audio,
    get_audio_min_score,
    yamnet_subgroup_for_label,
)
from App.Services.yamnet_service import YamnetService
from App.Services.memory_logs import memory_logs

logger = get_logger("yamnet.worker")

# custom_sound 매칭 디버그 로그를 너무 자주 찍지 않기 위한 간단한 throttle
_last_custom_debug_log_ts_by_sid: dict[str, int] = {}

# ✔️‼️커스텀 소리 매칭 임계값 ‼️✔️
# cosine similarity 값 스케일은 모델/환경/전처리에 따라 달라질 수 있어,
# 기본값을 낮춰 “아예 안 뜨는” 상황을 먼저 제거합니다.
CUSTOM_THRESHOLD = float(os.getenv("CUSTOM_SOUND_THRESHOLD", "0.70"))  # cosine similarity 임계값

# 커스텀 매칭은 소리가 들어올 때만 의미가 있습니다.
# (마이크가 아주 미세한 소음까지 계속 보내면 임베딩 유사도가 우연히 임계값을 넘을 수 있어 오탐 폭주 가능)
# rms가 너무 낮으면 커스텀 알림 브로드캐스트/DB저장을 스킵합니다.
CUSTOM_MIN_RMS = float(os.getenv("CUSTOM_SOUND_MIN_RMS", "0.005"))

# YAMNet CSV index: 개·동물·짖음 계열 (Animal=67 … Whimper (dog)=75, Growling=74)
_PET_SOUND_INDICES: tuple[int, ...] = (67, 68, 69, 70, 71, 72, 73, 74, 75)

# 보조 판별 시 이 라벨이 충분히 나오면 1위가 잡음·BGM·실내 등으로 밀린 경우에도 채택
_BARKISH_LABELS: frozenset[str] = frozenset(
    {
        "Bark",
        "Dog",
        "Bow-wow",
        "Yip",
        "Whimper (dog)",
        "Growling",
    }
)

# 1위가 생활알림이지만 개 짖음이 실제일 때 흔히 위로 뜨는 YAMNet 라벨
_CONFUSER_ALERT_LABELS: frozenset[str] = frozenset(
    {
        "Music",
        "Musical instrument",
        "Television",
        "Radio",
        "Environmental noise",
        "Noise",
        "Static",
        "White noise",
        "Pink noise",
        "Inside, small room",
        "Inside, large room or hall",
        "Inside, public space",
        "Silence",
        "Echo",
        "Cacophony",
        "Sound effect",
        "Pulse",
        "Hum",
    }
)


def _resolve_yamnet_classification(
    mean_sc: np.ndarray,
    index_to_label: dict[int, str],
) -> tuple[int, float, str, str | None, str | None]:
    """
    (top_i, top_score, label, event_type, keyword)
    1위가 말소리 스킵·BGM daily 등일 때 Bark 등이 약간 낮아도 채택.
    """
    min_sc = get_audio_min_score()
    floor_bark = max(0.20, min_sc * 0.55)

    top_i = int(np.argmax(mean_sc))
    top_score = float(mean_sc[top_i])
    label = index_to_label.get(top_i, str(top_i))
    event_type, keyword = classify_audio(top_i, top_score, label)

    pi = int(max(_PET_SOUND_INDICES, key=lambda ix: float(mean_sc[ix])))
    ps = float(mean_sc[pi])
    plabel = index_to_label.get(pi, str(pi))
    pet_et, pet_kw = classify_audio(pi, ps, plabel)

    if not pet_et or plabel not in _BARKISH_LABELS or ps < floor_bark:
        return top_i, top_score, label, event_type, keyword

    take_pet = False
    if event_type is None:
        take_pet = True
    elif event_type == "danger":
        take_pet = False
    elif event_type == "caution":
        if label in ("Animal", "Domestic animals, pets", "Dog") and ps + 0.04 >= top_score:
            take_pet = True
    elif event_type == "alert":
        if label in _CONFUSER_ALERT_LABELS:
            take_pet = True
        elif ps + 0.05 >= top_score:
            take_pet = True

    if take_pet:
        return pi, ps, plabel, pet_et, pet_kw
    return top_i, top_score, label, event_type, keyword


def _match_custom_sound(session_id: str, emb_live_candidates: list[np.ndarray]):
    """세션별 커스텀 사운드 중 후보 임베딩들(여러 1초 윈도우) 중 최대 유사도가 가장 큰 항목 찾기."""
    from App.db.database import SessionLocal
    from App.db.models import CustomSound
    from App.db.crud.custom_sounds import _blob_to_emb

    db = SessionLocal()
    try:
        rows = (
            db.query(CustomSound)
            .filter(CustomSound.client_session_uuid == session_id)
            .all()
        )
        best = None
        best_sim = 0.0
        usable_cnt = 0
        for r in rows:
            if not r.embed_blob or not r.embed_dim:
                continue
            usable_cnt += 1
            emb = _blob_to_emb(r.embed_blob, r.embed_dim)
            # 2개 후보 임베딩에 대해 최대 유사도 선택
            sims = [float(np.dot(c, emb)) for c in emb_live_candidates]
            sim = max(sims) if sims else 0.0
            if sim > best_sim:
                best_sim = sim
                best = r
        return best, best_sim, usable_cnt
    finally:
        db.close()


class AudioClsWorker:
    def __init__(self, queue: asyncio.Queue, broadcast_fn, persist_alert_fn, cooldown_check_fn):
        """
        broadcast_fn(sid, entry) : WS 브로드캐스트 함수(manager.broadcast_to_session 감싸면 됨)
        persist_alert_fn(sid, text, keyword, event_type, ts_ms, *, matched_custom_sound_id, custom_similarity) : DB 저장, event_id 반환
        cooldown_check_fn(sid, keyword, event_type, cooldown_sec, ts_ms)->bool : 쿨다운 True면 스킵
        """
        self.queue = queue
        self.yamnet = YamnetService()
        self.broadcast_fn = broadcast_fn
        self.persist_alert_fn = persist_alert_fn
        self.cooldown_check_fn = cooldown_check_fn

    async def run(self):
        logger.info("yamnet_worker_started")
        while True:
            item = await self.queue.get()
            try:
                sid = item["sid"]
                ts_ms = item["ts_ms"]
                audio = item["audio"]  # float32 16k (예: 4초 윈도우)
                conn_prefix = item.get("conn_prefix", "")
                # 커스텀 오탐 방지용: 입력 에너지(RMS) 계산
                audio_rms = float(np.sqrt(np.mean(np.square(audio))) + 1e-12)

                # handlers에서 미리 읽어 넣어준 값 사용 (db/스레드 혼용 방지)
                cooldown_sec = int(item.get("cooldown_sec", 5))
                alert_enabled = bool(item.get("alert_enabled", True))

                # 1) live embedding 구하기 (커스텀 사운드 매칭용)
                # 4초 윈도우 안에서 여러 1초 조각을 뽑아 그중 최대 유사도로 판정합니다.
                def _window_at(x: np.ndarray, start_sample: int) -> np.ndarray:
                    start_sample = int(start_sample)
                    end_sample = start_sample + 16000
                    if x.shape[0] >= end_sample and start_sample >= 0:
                        return x[start_sample:end_sample].astype(np.float32, copy=False)
                    # 부족한 구간은 0 패딩
                    if x.shape[0] <= start_sample:
                        return np.zeros((16000,), dtype=np.float32)
                    sliced = x[start_sample:min(end_sample, x.shape[0])]
                    pad = 16000 - sliced.shape[0]
                    if pad > 0:
                        sliced = np.pad(
                            sliced, (0, pad), mode="constant", constant_values=0.0
                        )
                    return sliced.astype(np.float32, copy=False)

                n = int(audio.shape[0])
                if n >= 4 * 16000:
                    offsets = [0, 16000, 32000, 48000]
                else:
                    max_start = max(0, n - 16000)
                    offsets = [0, max_start // 3, (2 * max_start) // 3, max_start]

                # 후보(중복 제거 후) 임베딩 계산
                uniq_offsets = []
                for o in offsets:
                    if o not in uniq_offsets:
                        uniq_offsets.append(o)
                emb_live_candidates: list[np.ndarray] = []
                for o in uniq_offsets:
                    win = _window_at(audio, o)
                    emb_live_candidates.append(
                        await asyncio.to_thread(self.yamnet.embedding_1s, win)
                    )

                best, best_sim, usable_cnt = await asyncio.to_thread(
                    _match_custom_sound, sid, emb_live_candidates
                )

                # 임계값 미달/미검출 원인(사용 가능한 임베딩 0건, sim 낮음 등)을 보기 위한 로그.
                # 너무 자주 찍히지 않도록 sid당 10초에 1회만 출력합니다.
                last_dbg = _last_custom_debug_log_ts_by_sid.get(sid, 0)
                if ts_ms - last_dbg > 10000:
                    logger.info(
                        "%s custom_match_debug sid=%s usable=%s best_id=%s sim=%.3f thr=%.3f",
                        conn_prefix,
                        sid,
                        usable_cnt,
                        getattr(best, "custom_sound_id", None),
                        best_sim,
                        CUSTOM_THRESHOLD,
                    )
                    _last_custom_debug_log_ts_by_sid[sid] = ts_ms
                if best is not None and best_sim >= CUSTOM_THRESHOLD and audio_rms >= CUSTOM_MIN_RMS:
                    logger.info(
                        "%s custom_match sid=%s custom_sound_id=%s name=%s event_type=%s sim=%.3f",
                        conn_prefix,
                        sid,
                        getattr(best, "custom_sound_id", None),
                        getattr(best, "name", None),
                        getattr(best, "event_type", None),
                        best_sim,
                    )
                    kw_custom = f"custom:{best.custom_sound_id}"
                    if not self.cooldown_check_fn(
                        sid, kw_custom, best.event_type, cooldown_sec, ts_ms
                    ):
                        text_custom = f"CustomSound:{best.name} (sim={best_sim:.2f})"
                        event_id = await asyncio.to_thread(
                            self.persist_alert_fn,
                            sid,
                            text_custom,
                            kw_custom,
                            best.event_type,
                            ts_ms,
                            matched_custom_sound_id=best.custom_sound_id,
                            custom_similarity=float(best_sim),
                        )
                        # Event-builder 통합: memory_logs에 추가 (최근 감지 로그·API 일관성)
                        _cat = {"danger": "warning", "caution": "caution", "alert": "daily"}.get(best.event_type, "daily")
                        _sub = (best.name or "").strip() or None
                        entry_custom = memory_logs.append_alert(
                            sid,
                            text_custom,
                            kw_custom,
                            best.event_type,
                            _cat,
                            float(best_sim),
                            ts_ms=ts_ms,
                            source="custom_sound",
                            subgroup=_sub,
                        )
                        if event_id is not None:
                            entry_custom["event_id"] = event_id
                        entry_custom["custom_sound_id"] = best.custom_sound_id
                        entry_custom["custom_similarity"] = best_sim
                        entry_custom["session_id"] = sid
                        entry_custom["ts_ms"] = ts_ms
                        if alert_enabled:
                            await self.broadcast_fn(sid, entry_custom)

                # 2) 기본 YAMNet 룰 분류(danger/alert)
                # TF는 블로킹이 커서 to_thread 권장. mean_scores 한 번으로 1위 + 개짖음 보조 판별.
                t0 = time.perf_counter()
                mean_sc = await asyncio.to_thread(self.yamnet.mean_scores, audio)
                dt_ms = int((time.perf_counter() - t0) * 1000)
                add_time("yamnet", dt_ms)

                top_i, top_score, label, event_type, keyword = _resolve_yamnet_classification(
                    mean_sc, self.yamnet.index_to_label
                )
                logger.debug(
                    "%s YAMNET top=%s score=%.3f label=%s mapped=%s",
                    conn_prefix,
                    top_i,
                    top_score,
                    label,
                    event_type,
                )

                if not event_type:
                    continue

                # prefix는 worker에서 한 번만 (쿨다운/record_alert_ts 키 일치)
                kw_prefixed = f"yamnet:{keyword}"

                if self.cooldown_check_fn(
                    sid, kw_prefixed, event_type, cooldown_sec, ts_ms
                ):
                    continue

                # label은 YamnetService.predict()에서 index_to_label로 반환됨
                text = f"Audio: {label} ({top_score:.2f})"

                # DB 저장 (to_thread로 이벤트 루프 블로킹 방지), event_id 반환
                event_id = await asyncio.to_thread(
                    self.persist_alert_fn, sid, text, kw_prefixed, event_type, ts_ms
                )

                # Event-builder 통합: memory_logs에 추가
                category = {"danger": "warning", "caution": "caution", "alert": "daily"}.get(event_type, "daily")
                subgroup_ui = yamnet_subgroup_for_label(label or "") or None
                entry = memory_logs.append_alert(
                    sid, text, kw_prefixed, event_type, category,
                    float(top_score), ts_ms=ts_ms, source="audio",
                    subgroup=subgroup_ui,
                )
                if event_id is not None:
                    entry["event_id"] = event_id
                entry["label"] = label
                entry["label_index"] = top_i

                # WS 발행
                if alert_enabled:
                    await self.broadcast_fn(sid, entry)

            except Exception:
                logger.exception("yamnet_worker_failed")
            finally:
                inc("yamnet_processed")
                self.queue.task_done()