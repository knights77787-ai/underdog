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
from App.Services.event_type_utils import event_type_to_category
from App.Services.yamnet_service import YamnetService
from App.Services.memory_logs import memory_logs

logger = get_logger("yamnet.worker")

# custom_sound 매칭 디버그 로그를 너무 자주 찍지 않기 위한 간단한 throttle
_last_custom_debug_log_ts_by_sid: dict[str, int] = {}
_last_custom_pick_by_sid: dict[str, tuple[int, int]] = {}  # sid -> (custom_sound_id, ts_ms)

# ✔️ 커스텀 매칭 핵심 튜닝값
# - 기본 임계값: CUSTOM_THRESHOLD
# - 큰 소리 구간 임계값: CUSTOM_THRESHOLD_LOUD (RMS 기준)
# - 개별 등록음 임계값(match_threshold)이 있으면 위 전역값보다 우선
CUSTOM_THRESHOLD = float(os.getenv("CUSTOM_SOUND_THRESHOLD", "0.75"))
# 입력 음압이 충분히 큰 구간은 커스텀 임계값을 약간 완화해 미탐을 줄입니다.
CUSTOM_THRESHOLD_LOUD = float(os.getenv("CUSTOM_SOUND_THRESHOLD_LOUD", "0.75"))
CUSTOM_LOUD_RMS = float(os.getenv("CUSTOM_SOUND_LOUD_RMS", "0.020"))
# 음성(사람 말) 구간에서는 커스텀 오탐이 매우 잘 나므로, 충분히 강한 sim가 아니면 커스텀을 막습니다.
CUSTOM_SPEECH_BLOCK_SCORE = float(os.getenv("CUSTOM_SOUND_SPEECH_BLOCK_SCORE", "0.38"))
CUSTOM_SPEECH_ALLOW_STRONG_SIM = float(os.getenv("CUSTOM_SOUND_SPEECH_ALLOW_STRONG_SIM", "0.62"))
CUSTOM_STICKY_SEC = int(os.getenv("CUSTOM_SOUND_STICKY_SEC", "8"))
CUSTOM_STICKY_SIM_GAP = float(os.getenv("CUSTOM_SOUND_STICKY_SIM_GAP", "0.03"))

# 커스텀 매칭은 소리가 들어올 때만 의미가 있습니다.
# (마이크가 아주 미세한 소음까지 계속 보내면 임베딩 유사도가 우연히 임계값을 넘을 수 있어 오탐 폭주 가능)
# rms가 너무 낮으면 커스텀 알림 브로드캐스트/DB저장을 스킵합니다.
CUSTOM_MIN_RMS = float(os.getenv("CUSTOM_SOUND_MIN_RMS", "0.022"))

# 등록이 2개 이상일 때 1위·2위 유사도 차가 이 미만이고,
# 1위 sim도 STRONG 미만이면 “배경에서 임의로 한 라벨이 이긴” 것으로 보고 커스텀 알림을 내지 않습니다.
CUSTOM_TOP2_MIN_GAP = float(os.getenv("CUSTOM_SOUND_TOP2_MIN_GAP", "0.08"))
CUSTOM_STRONG_SIM = float(os.getenv("CUSTOM_SOUND_STRONG_SIM", "0.70"))

# 동일 커스텀 소리는 한 번 울린 뒤 최소 이 간격(초) 동안은 다시 알림하지 않습니다.
# (일반 cooldown_sec가 5초인데 4초 윈도우가 ~6초마다 들어오면 매번 쿨다운이 풀려 연속 알림이 납니다.)
CUSTOM_COOLDOWN_SEC = int(os.getenv("CUSTOM_SOUND_COOLDOWN_SEC", "15"))

# 등록 커스텀이 2개 이상일 때 1·2위 유사도가 이 정도로 붙으면 "애매"로 보고 아래 펫 보조/스킵 로직을 탑니다.
CUSTOM_AMBIGUITY_MARGIN = float(os.getenv("CUSTOM_SOUND_AMBIGUITY_MARGIN", "0.12"))
# 애매한데 1위가 생활알림(alert)·2위가 경고/주의일 때, 2위가 1위와 이 정도 이내로 붙어 있으면 2위(펫 쪽)를 우선합니다.
CUSTOM_PET_TIGHT_GAP = float(os.getenv("CUSTOM_SOUND_PET_TIGHT_GAP", "0.06"))
# 펫 대역(mean_sc) 최대값이 이 이상일 때만 위 우선/스킵을 적용합니다.
CUSTOM_PET_ASSIST_MIN = float(os.getenv("CUSTOM_SOUND_PET_ASSIST_MIN", "0.18"))

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

_SPEECHISH_LABELS: frozenset[str] = frozenset(
    {
        "Speech",
        "Conversation",
        "Narration, monologue",
        "Female speech, woman speaking",
        "Male speech, man speaking",
        "Child speech, kid speaking",
        "Babbling",
        "Speech synthesizer",
        "Shout",
        "Yell",
        "Whispering",
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


def _rank_custom_sounds_by_similarity(
    session_id: str, emb_live_candidates: list[np.ndarray]
) -> tuple[list[tuple[object, float]], int]:
    """세션별 커스텀 사운드마다 live 후보 임베딩과의 최대 유사도를 구하고, sim 내림차순으로 정렬."""
    from App.db.database import SessionLocal
    from App.db.crud.embed_codec import blob_to_emb
    from App.db.models import CustomSound

    db = SessionLocal()
    try:
        rows = (
            db.query(CustomSound)
            .filter(CustomSound.client_session_uuid == session_id)
            .all()
        )
        ranked: list[tuple[object, float]] = []
        usable_cnt = 0
        for r in rows:
            if not r.embed_blob or not r.embed_dim:
                continue
            usable_cnt += 1
            emb = blob_to_emb(r.embed_blob, r.embed_dim)
            sims = [float(np.dot(c, emb)) for c in emb_live_candidates]
            sim = max(sims) if sims else 0.0
            ranked.append((r, sim))
        ranked.sort(key=lambda t: -t[1])
        return ranked, usable_cnt
    finally:
        db.close()


def _resolve_custom_pick(
    ranked: list[tuple[object, float]],
    mean_sc: np.ndarray,
) -> tuple[object | None, float, str]:
    """
    유사도 순위만으로는 열차(alert)가 개 짖음(danger)보다 우연히 위로 올라가는 경우가 있어,
    1·2위가 애매할 때 YAMNet 펫 대역 점수로 생활알림보다 경고/주의 등록을 우선하거나, 커스텀을 포기합니다.

    Returns: (row_or_none, sim, reason) reason: "top" | "pet_prefer" | "skip_ambiguous_pet"
    """
    if not ranked:
        return None, 0.0, "top"
    r0, s0 = ranked[0]
    if len(ranked) == 1:
        return r0, s0, "top"

    r1, s1 = ranked[1]
    et0 = (getattr(r0, "event_type", None) or "").strip()
    et1 = (getattr(r1, "event_type", None) or "").strip()

    gap = s0 - s1
    # 1·2위가 매우 근접(sim 동률) + 1위 sim도 충분히 강하지 않으면 배경/잡음 패턴으로 간주.
    # CUSTOM_STRONG_SIM은 "동률이어도 통과 가능한 강한 매칭" 기준으로 사용합니다.
    low_sim_floor = max(CUSTOM_STRONG_SIM, CUSTOM_THRESHOLD - 0.02, 0.30)
    if gap < CUSTOM_TOP2_MIN_GAP and s0 < low_sim_floor:
        return None, 0.0, "skip_ambiguous_multi"

    if s0 - s1 >= CUSTOM_AMBIGUITY_MARGIN:
        return r0, s0, "top"

    pet_score = float(max(float(mean_sc[ix]) for ix in _PET_SOUND_INDICES))

    # 애매 + 1위 생활알림 + 2위 경고/주의 + 펫 신호: 짖음 쪽 등록을 우선
    if (
        pet_score >= CUSTOM_PET_ASSIST_MIN
        and et0 == "alert"
        and et1 in ("danger", "caution")
    ):
        if s1 >= s0 - CUSTOM_PET_TIGHT_GAP:
            return r1, s1, "pet_prefer"
        # 1위만 유사도가 튀고 펫 신호는 강함 → 잘못된 커스텀(열차)일 가능성, YAMNet 경로에 맡김
        return None, 0.0, "skip_ambiguous_pet"

    return r0, s0, "top"


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

                # 0) YAMNet mean_scores는 먼저 구해서 이후 YAMNet 알림 분류에 재사용합니다.
                #    (커스텀 소리는 클락션·초인종 등 비-펫도 등록하므로 pet_score 게이트는 쓰지 않습니다.)
                t0 = time.perf_counter()
                mean_sc = await asyncio.to_thread(self.yamnet.mean_scores, audio)
                dt_ms = int((time.perf_counter() - t0) * 1000)
                add_time("yamnet", dt_ms)

                top_i, top_score, label, event_type, keyword = _resolve_yamnet_classification(
                    mean_sc, self.yamnet.index_to_label
                )

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

                ranked, usable_cnt = await asyncio.to_thread(
                    _rank_custom_sounds_by_similarity, sid, emb_live_candidates
                )
                best, best_sim, pick_reason = _resolve_custom_pick(ranked, mean_sc)
                # 직전 승자와 점수가 거의 비슷하면 짧은 구간 라벨 점프를 줄이기 위해 직전 승자를 유지합니다.
                prev_pick = _last_custom_pick_by_sid.get(sid)
                if (
                    prev_pick is not None
                    and ranked
                    and (ts_ms - int(prev_pick[1])) <= CUSTOM_STICKY_SEC * 1000
                ):
                    prev_id = int(prev_pick[0])
                    r0_id = int(getattr(ranked[0][0], "custom_sound_id", -1))
                    if r0_id != prev_id:
                        prev_row = next(
                            (row for row, _sim in ranked if int(getattr(row, "custom_sound_id", -1)) == prev_id),
                            None,
                        )
                        prev_sim = next(
                            (float(_sim) for row, _sim in ranked if int(getattr(row, "custom_sound_id", -1)) == prev_id),
                            0.0,
                        )
                        if prev_row is not None and prev_sim >= float(ranked[0][1]) - CUSTOM_STICKY_SIM_GAP:
                            best, best_sim, pick_reason = prev_row, prev_sim, "sticky_prev"
                # keyword가 None이면 (False or None)이 되어 None이 될 수 있음 → bool로 고정
                is_speech_dominant = bool(
                    (label in _SPEECHISH_LABELS and top_score >= CUSTOM_SPEECH_BLOCK_SCORE)
                    or (keyword and str(keyword).startswith("speech:"))
                )

                # 임계값 미달/미검출 원인(사용 가능한 임베딩 0건, sim 낮음 등)을 보기 위한 로그.
                # 너무 자주 찍히지 않도록 sid당 10초에 1회만 출력합니다.
                last_dbg = _last_custom_debug_log_ts_by_sid.get(sid, 0)
                if ts_ms - last_dbg > 10000:
                    _r0 = ranked[0] if ranked else None
                    _r1 = ranked[1] if len(ranked) > 1 else None
                    dbg_eff_thr = (
                        CUSTOM_THRESHOLD_LOUD
                        if audio_rms >= CUSTOM_LOUD_RMS
                        else CUSTOM_THRESHOLD
                    )
                    logger.info(
                        "%s custom_match_debug sid=%s usable=%s pick=%s id1=%s s1=%.3f id2=%s s2=%.3f thr=%.3f rms=%.4f speech=%s top_label=%s top=%.3f",
                        conn_prefix,
                        sid,
                        usable_cnt,
                        pick_reason,
                        getattr(_r0[0], "custom_sound_id", None) if _r0 else None,
                        float(_r0[1]) if _r0 else 0.0,
                        getattr(_r1[0], "custom_sound_id", None) if _r1 else None,
                        float(_r1[1]) if _r1 else 0.0,
                        dbg_eff_thr,
                        audio_rms,
                        int(is_speech_dominant),
                        label,
                        top_score,
                    )
                    _last_custom_debug_log_ts_by_sid[sid] = ts_ms
                eff_threshold = (
                    CUSTOM_THRESHOLD_LOUD
                    if audio_rms >= CUSTOM_LOUD_RMS
                    else CUSTOM_THRESHOLD
                )
                threshold_for_best = (
                    float(getattr(best, "match_threshold", 0.0))
                    if best is not None and getattr(best, "match_threshold", None) is not None
                    else eff_threshold
                )
                if (
                    best is not None
                    and best_sim >= threshold_for_best
                    and audio_rms >= CUSTOM_MIN_RMS
                    and (not is_speech_dominant or best_sim >= CUSTOM_SPEECH_ALLOW_STRONG_SIM)
                ):
                    logger.info(
                        "%s custom_match sid=%s custom_sound_id=%s name=%s event_type=%s sim=%.3f thr=%.3f rms=%.4f pick=%s",
                        conn_prefix,
                        sid,
                        getattr(best, "custom_sound_id", None),
                        getattr(best, "name", None),
                        getattr(best, "event_type", None),
                        best_sim,
                        threshold_for_best,
                        audio_rms,
                        pick_reason,
                    )
                    _last_custom_pick_by_sid[sid] = (
                        int(getattr(best, "custom_sound_id", 0)),
                        ts_ms,
                    )
                    kw_custom = f"custom:{best.custom_sound_id}"
                    custom_cd = max(cooldown_sec, CUSTOM_COOLDOWN_SEC)
                    if not self.cooldown_check_fn(
                        sid, kw_custom, best.event_type, custom_cd, ts_ms
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
                            custom_threshold_used=float(threshold_for_best),
                            custom_rms=float(audio_rms),
                            custom_pick_reason=str(pick_reason),
                        )
                        # Event-builder 통합: memory_logs에 추가 (최근 감지 로그·API 일관성)
                        _cat = event_type_to_category(best.event_type)
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
                category = event_type_to_category(event_type)
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