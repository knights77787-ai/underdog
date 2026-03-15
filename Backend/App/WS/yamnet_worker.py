# app/WS/yamnet_worker.py
import asyncio
import time
from App.Core.logging import get_logger
from App.Services.yamnet_service import YamnetService
from App.Services.audio_rules import classify_audio

logger = get_logger("ws.yamnet")

class YamnetWorker:
    def __init__(self, queue: asyncio.Queue):
        self.queue = queue
        self.yamnet = YamnetService()  # TFHub 로드(1회)

    async def run(self):
        logger.info("yamnet_worker_started")
        while True:
            item = await self.queue.get()
            try:
                sid = item["sid"]
                ts_ms = item.get("ts_ms") or int(time.time() * 1000)
                audio = item["audio"]  # float32 16k (대략 1초=16000)
                conn_prefix = item.get("conn_prefix", "")

                cooldown_sec = int(item.get("cooldown_sec", 5))
                alert_enabled = bool(item.get("alert_enabled", True))

                # 1) YAMNet 분류 (CPU 블로킹 -> to_thread)
                top_i, top_score = await asyncio.to_thread(self.yamnet.predict_index, audio)

                # 2) 룰 매핑 -> danger/alert/None
                event_type, keyword = classify_audio(top_i, top_score)
                logger.debug(
                    "%s YAMNET top=%s score=%.3f mapped=%s",
                    conn_prefix, top_i, top_score, event_type
                )
                if not event_type:
                    continue

                # keyword는 충돌 방지용 prefix 추천
                keyword2 = f"yamnet:{keyword}"

                # 3) 쿨다운/DB/WS는 handlers의 함수 재사용
                from App.WS.handlers import _is_in_cooldown, record_alert_ts, _persist_alert
                from App.WS.manager import manager

                if _is_in_cooldown(sid, keyword2, event_type, cooldown_sec, ts_ms):
                    continue

                record_alert_ts(sid, keyword2, event_type, ts_ms)

                # DB 저장(텍스트는 요약) → event_id 반환받아 WS에 포함 (프론트 피드백용)
                text = f"AudioIndex:{top_i} ({top_score:.2f})"
                event_id = await asyncio.to_thread(
                    _persist_alert, sid, text, keyword2, event_type, ts_ms
                )

                # WS 브로드캐스트
                if alert_enabled:
                    entry = {
                        "type": "alert",
                        "source": "audio",
                        "event_type": event_type,
                        "keyword": keyword2,
                        "label_index": top_i,
                        "score": top_score,
                        "text": text,
                        "session_id": sid,
                        "ts_ms": ts_ms,
                    }
                    if event_id is not None:
                        entry["event_id"] = event_id
                    await manager.broadcast_to_session(sid, entry)

            except Exception:
                logger.exception("yamnet_worker_failed")
            finally:
                self.queue.task_done()