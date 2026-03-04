# App/WS/audio_cls_worker.py
# db 세션은 worker에 넘기지 말고, settings는 handlers에서 미리 읽어 item에 값만 넘김.
import asyncio
import time
import numpy as np

from App.Core.logging import get_logger
from App.Core.metrics import add_time, inc
from App.Services.audio_rules import classify_audio
from App.Services.yamnet_service import YamnetService

logger = get_logger("yamnet.worker")

CUSTOM_THRESHOLD = 0.80  # 코사인 유사도 임계값 (0.75~0.9 사이에서 조정 가능)


def _match_custom_sound(session_id: str, emb_live: np.ndarray):
    """세션별 커스텀 사운드 중 emb_live와 가장 유사한 항목 찾기."""
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
        for r in rows:
            if not r.embed_blob or not r.embed_dim:
                continue
            emb = _blob_to_emb(r.embed_blob, r.embed_dim)
            sim = float(np.dot(emb_live, emb))
            if sim > best_sim:
                best_sim = sim
                best = r
        return best, best_sim
    finally:
        db.close()


class AudioClsWorker:
    def __init__(self, queue: asyncio.Queue, broadcast_fn, persist_alert_fn, cooldown_check_fn):
        """
        broadcast_fn(sid, entry) : WS 브로드캐스트 함수(manager.broadcast_to_session 감싸면 됨)
        persist_alert_fn(sid, text, keyword, event_type, ts_ms) : DB 저장 함수
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
                audio = item["audio"]  # float32 16k (16000,)
                conn_prefix = item.get("conn_prefix", "")

                # handlers에서 미리 읽어 넣어준 값 사용 (db/스레드 혼용 방지)
                cooldown_sec = int(item.get("cooldown_sec", 5))
                alert_enabled = bool(item.get("alert_enabled", True))

                # 1) live embedding 구하기 (커스텀 사운드 매칭용)
                emb_live = await asyncio.to_thread(self.yamnet.embedding_1s, audio)
                best, best_sim = await asyncio.to_thread(
                    _match_custom_sound, sid, emb_live
                )
                if best is not None and best_sim >= CUSTOM_THRESHOLD:
                    kw_custom = f"custom:{best.custom_sound_id}"
                    if not self.cooldown_check_fn(
                        sid, kw_custom, best.event_type, cooldown_sec, ts_ms
                    ):
                        text_custom = f"CustomSound:{best.name} (sim={best_sim:.2f})"
                        await asyncio.to_thread(
                            self.persist_alert_fn,
                            sid,
                            text_custom,
                            kw_custom,
                            best.event_type,
                            ts_ms,
                        )
                        if alert_enabled:
                            entry_custom = {
                                "type": "alert",
                                "source": "audio",
                                "event_type": best.event_type,
                                "keyword": kw_custom,
                                "custom_sound_id": best.custom_sound_id,
                                "custom_similarity": best_sim,
                                "text": text_custom,
                                "session_id": sid,
                                "ts_ms": ts_ms,
                            }
                            await self.broadcast_fn(sid, entry_custom)

                # 2) 기본 YAMNet 룰 분류(danger/alert)
                # TF는 블로킹이 커서 to_thread 권장 (predict는 index, score, label 반환)
                t0 = time.perf_counter()
                top_i, top_score, label = await asyncio.to_thread(self.yamnet.predict, audio)
                dt_ms = int((time.perf_counter() - t0) * 1000)
                add_time("yamnet", dt_ms)

                event_type, keyword = classify_audio(top_i, top_score, label)
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

                # prefix는 worker에서 한 번만 (쿨डाउन/record_alert_ts 키 일치)
                kw_prefixed = f"yamnet:{keyword}"

                if self.cooldown_check_fn(
                    sid, kw_prefixed, event_type, cooldown_sec, ts_ms
                ):
                    continue

                # label은 YamnetService.predict()에서 index_to_label로 반환됨
                text = f"Audio: {label} ({top_score:.2f})"

                # DB 저장 (to_thread로 이벤트 루프 블로킹 방지)
                await asyncio.to_thread(
                    self.persist_alert_fn, sid, text, kw_prefixed, event_type, ts_ms
                )

                # WS 발행 (keyword는 DB/쿨다운과 동일하게 kw_prefixed로 통일, label 추가)
                if alert_enabled:
                    entry = {
                        "type": "alert",
                        "source": "audio",
                        "event_type": event_type,
                        "keyword": kw_prefixed,
                        "label": label,
                        "label_index": top_i,
                        "score": top_score,
                        "text": text,
                        "session_id": sid,
                        "ts_ms": ts_ms,
                    }
                    await self.broadcast_fn(sid, entry)

            except Exception:
                logger.exception("yamnet_worker_failed")
            finally:
                inc("yamnet_processed")
                self.queue.task_done()