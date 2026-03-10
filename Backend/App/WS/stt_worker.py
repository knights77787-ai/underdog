"""STT 큐 소비 워커: VAD_END로 들어온 음성만 직렬로 Whisper 처리."""
import asyncio
import time

from App.Core.logging import get_logger
from App.Core.metrics import add_time, inc

logger = get_logger("ws.stt_worker")


class SttWorker:
    """STT_QUEUE에서 아이템을 꺼내 Whisper로 변환 후 caption/alert 처리."""

    def __init__(self, queue: asyncio.Queue):
        self._queue = queue

    async def run(self) -> None:
        from App.WS import handlers

        logger.info("stt_worker_started")
        while True:
            try:
                item = await self._queue.get()
            except asyncio.CancelledError:
                logger.info("stt_worker_cancelled")
                raise
            try:
                logger.info(
                    "STT INPUT sid=%s samples=%s dtype=%s",
                    item["sid"],
                    item["speech_audio"].shape[0] if item["speech_audio"] is not None else -1,
                    getattr(item["speech_audio"], "dtype", None),
                )
                t0 = time.perf_counter()
                beam_size = item.get("beam_size")
                text = await asyncio.to_thread(
                    handlers.WHISPER.transcribe_16k_f32,
                    item["speech_audio"],
                    beam_size,
                )
                dt_ms = int((time.perf_counter() - t0) * 1000)
                add_time("stt", dt_ms)
                if text:
                    logger.info(
                        "STT_TEXT sid=%s text_len=%s text=%s",
                        item["sid"],
                        len(text),
                        text[:60],
                    )
                    await handlers._handle_caption_generated(
                        websocket=item["websocket"],
                        sid=item["sid"],
                        text=text,
                        ts_ms=item["ts_ms"],
                        conn_prefix=item["conn_prefix"],
                    )
                else:
                    logger.info(
                        "STT_EMPTY sid=%s speech_samples=%s",
                        item["sid"],
                        item["speech_audio"].shape[0],
                    )
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("STT_FAILED sid=%s", item["sid"])
            finally:
                inc("stt_processed")
