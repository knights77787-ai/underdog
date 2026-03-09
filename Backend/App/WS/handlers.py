"""
WebSocket 메시지 처리: join, caption(저장/브로드캐스트) + alert(판정 시에만 추가).

저장·브로드캐스트 흐름(현실 운영):
  A) caption(pass) 무조건 저장 + WS 브로드캐스트
  B) 판정 결과가 있으면(warning/daily) alert 추가 저장 + WS (쿨다운·alert_enabled 반영)
  C) 쿨다운: (client_session_uuid, keyword, event_type) 동일 시 cooldown_sec 내엔 alert 저장/발행 스킵
  키워드 없으면 caption(pass)만 남고 alert 이벤트는 저장하지 않음.
"""
import asyncio
import time

import numpy as np
from fastapi import WebSocket

from App.Core.logging import get_logger
from App.Core.metrics import inc
from App.Services import keyword_detector
from App.Services.stt_whisper import WhisperConfig, WhisperSTT
from App.Services.vad_silero import SileroVADStream, VADConfig
from App.WS.audio_buffer import decode_pcm16_b64, i16_to_f32
from App.WS.audio_state import AudioState, AudioStateStore
from App.WS.manager import manager
from App.Services.memory_logs import memory_logs
from App.Services.custom_phrase_matcher import match_phrase

logger = get_logger("ws.handlers")
persist_logger = get_logger("ws.persist")
audio_logger = get_logger("ws.audio")

# 전역(프로세스) VAD 스트림 + 세션별 오디오 상태
VAD_STREAM = SileroVADStream(
    VADConfig(sr=16000, threshold=0.5, min_silence_ms=300, speech_pad_ms=30)
)
AUDIO_STATES = AudioStateStore()
WHISPER = WhisperSTT(WhisperConfig(model_name="base", language="ko"))
# 비말(1초) 오디오 분류용 큐. maxsize로 폭주 방지
AUDIOCLS_QUEUE: asyncio.Queue = asyncio.Queue(maxsize=20)
# STT 직렬화: VAD_END → 큐 → 단일 워커가 Whisper 실행 (동시 다중 STT 방지)
STT_QUEUE: asyncio.Queue = asyncio.Queue(maxsize=8)

# 쿨다운: (session_id, keyword, event_type) -> 마지막 발행 ts_ms (스펙과 동일)
# disconnect 시 해당 세션 키 제거해 메모리 누적 완화
_last_alert_ts_by_key: dict[tuple[str, str, str], int] = {}


def clear_cooldown_for_session(session_id: str) -> None:
    """세션 disconnect 시 해당 세션의 쿨다운·설정 캐시 제거 (메모리 보강)."""
    to_del = [k for k in _last_alert_ts_by_key if k[0] == session_id]
    for k in to_del:
        del _last_alert_ts_by_key[k]
    _settings_cache.pop(session_id, None)


def record_alert_ts(session_id: str, keyword: str, event_type: str, ts_ms: int) -> None:
    """alert 발행 시 쿨다운용 타임스탬프 기록 (worker 등에서 호출)."""
    _last_alert_ts_by_key[(session_id, keyword or "", event_type)] = ts_ms


# 세션별 설정 캐시 (TTL 10초). caption/alert 판정 시 DB 조회 완화
_settings_cache_ttl_sec = 10
_settings_cache: dict[str, tuple[dict, float]] = {}  # client_session_uuid -> (settings, cached_at)


def _get_settings(client_session_uuid: str) -> dict:
    """세션 설정 조회. 세션별 10초 캐시로 DB 조회 완화."""
    now = time.monotonic()
    entry = _settings_cache.get(client_session_uuid)
    if entry is not None:
        cached, cached_at = entry
        if now - cached_at < _settings_cache_ttl_sec:
            return cached
    from App.db.crud import settings as crud_settings
    from App.db.database import SessionLocal

    db = SessionLocal()
    try:
        settings = crud_settings.get_settings(db, client_session_uuid)
        _settings_cache[client_session_uuid] = (settings, now)
        return settings
    finally:
        db.close()


def _persist_caption(client_session_uuid: str, text: str, ts_ms: int) -> None:
    from App.db.crud import events as crud_events
    from App.db.database import SessionLocal

    db = SessionLocal()
    try:
        crud_events.create_caption_event(db, client_session_uuid, text, ts_ms)
    except Exception:
        db.rollback()
        persist_logger.exception(
            "db_save_caption_failed",
            extra={
                "session_id": client_session_uuid,
                "ts_ms": ts_ms,
                "text_len": len(text),
            },
        )
        raise
    finally:
        db.close()


def _persist_alert(
    client_session_uuid: str,
    text: str,
    keyword: str | None,
    event_type: str,
    ts_ms: int,
) -> int | None:
    """alert 이벤트 DB 저장. 성공 시 event_id 반환 (WS 브로드캐스트용)."""
    from App.db.crud import events as crud_events
    from App.db.database import SessionLocal

    db = SessionLocal()
    try:
        event_id = crud_events.create_alert_event(
            db, client_session_uuid, text, keyword or "", event_type, ts_ms
        )
        return event_id
    except Exception:
        db.rollback()
        persist_logger.exception(
            "db_save_alert_failed",
            extra={
                "session_id": client_session_uuid,
                "event_type": event_type,
                "keyword": keyword,
                "text_len": len(text),
            },
        )
        raise
    finally:
        db.close()


def _is_in_cooldown(
    sid: str, keyword: str, event_type: str, cooldown_sec: int, ts_ms: int
) -> bool:
    """(sid, keyword, event_type) 쿨다운 여부. ts_ms 기준으로 비교."""
    key = (sid, keyword or "", event_type)
    last_ts = _last_alert_ts_by_key.get(key, 0)
    return last_ts + cooldown_sec * 1000 > ts_ms


async def _handle_caption_generated(
    *,
    websocket: WebSocket,
    sid: str,
    text: str,
    ts_ms: int,
    conn_prefix: str,
) -> None:
    """caption 텍스트 공통 처리: 브로드캐스트·DB 저장·키워드 판정·alert(쿨다운·설정 반영). STT 결과도 동일 흐름."""
    # 1) caption 브로드캐스트 (말한/입력한 클라이언트도 자막 보이도록 exclude 없이 전송)
    caption_entry = memory_logs.append_caption(sid, text, ts_ms=ts_ms)
    await manager.broadcast_to_session(sid, caption_entry)
    # 2) DB 저장
    await asyncio.to_thread(_persist_caption, sid, text, ts_ms)
    # 3) 키워드 판정
    category, event_type, keyword, score = keyword_detector.judge(text)
    if event_type not in ("danger", "alert") or not keyword:
        return
    # 4) 설정 기반 쿨다운·alert on/off
    settings = await asyncio.to_thread(_get_settings, sid)
    cooldown_sec = int(settings.get("cooldown_sec", 5))
    alert_enabled = bool(settings.get("alert_enabled", True))
    if _is_in_cooldown(sid, keyword or "", event_type, cooldown_sec, ts_ms):
        logger.debug(
            f"{conn_prefix}alert_skipped reason=cooldown session_id={sid} keyword={keyword or ''} event_type={event_type}"
        )
        return
    # 5) alert 저장 + (가능하면) WS 발행 (event_id 포함해 프론트 피드백용)
    _last_alert_ts_by_key[(sid, keyword or "", event_type)] = ts_ms
    entry = memory_logs.append_alert(
        sid, text, keyword or "", event_type, category, score, ts_ms=ts_ms, source="text"
    )
    event_id = await asyncio.to_thread(_persist_alert, sid, text, keyword, event_type, ts_ms)
    if event_id is not None:
        entry["event_id"] = event_id
        # 항상 클라이언트에 event_id 전달 (맞아요/아니에요 동작). 알림 끄면 silent로 토스트만 생략
        if not alert_enabled:
            entry["silent"] = True
        await manager.broadcast_to_session(sid, entry)
        logger.info(
            f"{conn_prefix}ws_alert_emitted session_id={sid} keyword={keyword or ''} event_type={event_type} event_id={event_id} silent={not alert_enabled}"
        )
    else:
        logger.debug(
            f"{conn_prefix}alert_not_broadcast event_id=None session_id={sid} keyword={keyword or ''}"
        )


async def handle_message(
    websocket: WebSocket,
    msg: dict,
    session_id: str | None,
    conn_id: str | None = None,
) -> str | None:
    msg_type = msg.get("type")
    conn_prefix = f"[conn={conn_id}] " if conn_id else ""

    if msg_type == "join":
        sid = msg.get("session_id")
        if sid:
            await manager.connect(websocket, sid)
            await websocket.send_json({"type": "join_ack", "session_id": sid})
            logger.info(f"{conn_prefix}ws_join session_id={sid} client={websocket.client}")
            return sid
        return session_id

    if msg_type == "audio_chunk":
        sid = msg.get("session_id")
        ts_ms = msg.get("ts_ms") or int(time.time() * 1000)
        sr = msg.get("sr")
        fmt = msg.get("format")
        b64 = msg.get("data_b64")
        if not sid or not b64:
            return session_id
        if sr != 16000 or fmt != "pcm_s16le":
            audio_logger.warning(
                "bad_audio_format session_id=%s sr=%s format=%s",
                sid, sr, fmt,
            )
            return session_id
        # 1) Decode base64 → float32
        try:
            audio_i16 = decode_pcm16_b64(b64)
            audio_f32 = i16_to_f32(audio_i16)
        except Exception:
            audio_logger.exception("audio_decode_failed session_id=%s", sid)
            return session_id
        # 2) 세션별 AudioState (VADIterator + speech 수집)
        st = AUDIO_STATES.get(sid)
        if st is None:
            st = AudioState(vad_it=VAD_STREAM.new_iterator())
            AUDIO_STATES.set(sid, st)
            audio_logger.info("audio_state_created session_id=%s", sid)
        # 3) VAD feed
        try:
            vad_ev = VAD_STREAM.feed(st.vad_it, audio_f32)
        except Exception:
            audio_logger.exception("vad_failed session_id=%s", sid)
            return session_id
        # 4) speech start/end 수집 → VAD_START / VAD_END 로그
        if vad_ev is not None:
            # end 먼저 처리 (한 이벤트에 start+end 동시에 올 수 있음)
            if "end" in vad_ev and st.in_speech:
                st.in_speech = False
                speech_audio = (
                    np.concatenate(st.speech_chunks)
                    if st.speech_chunks
                    else np.zeros((0,), dtype=np.float32)
                )
                st.speech_chunks = []
                audio_logger.info(
                    "VAD_END session_id=%s ts_ms=%s samples=%s",
                    sid, ts_ms, speech_audio.shape[0],
                )
                # 너무 짧은 음성은 Whisper에 안 보냄 (노이즈/헛발화 방지)
                min_samples = int(16000 * 0.3)
                if speech_audio.shape[0] < min_samples:
                    audio_logger.info(
                        "%s STT_SKIP_SHORT sid=%s samples=%s",
                        conn_prefix, sid, speech_audio.shape[0],
                    )
                else:
                    # 너무 조용한 구간 스킵 (RMS 기준, Whisper 환각 방지)
                    rms = float(np.sqrt(np.mean(np.square(speech_audio))) + 1e-12)
                    if rms < 0.008:
                        audio_logger.info(
                            "%s STT_SKIP_SILENT sid=%s rms=%.4f",
                            conn_prefix, sid, rms,
                        )
                    else:
                        # 최대 길이 컷 (Whisper 지연 방지, MVP 8~10초 권장)
                        max_samples = 16000 * 10
                        if speech_audio.shape[0] > max_samples:
                            speech_audio = speech_audio[-max_samples:]
                            audio_logger.info(
                                "%s STT_CUT sid=%s max_sec=10",
                                conn_prefix, sid,
                            )
                        # 4-1) 커스텀 구문 매칭 (Whisper encoder embedding 기반)
                        try:
                            best_phrase, sim = await asyncio.to_thread(
                                match_phrase, sid, speech_audio
                            )
                        except Exception:
                            audio_logger.exception(
                                "%s PHRASE_MATCH_FAILED sid=%s", conn_prefix, sid
                            )
                            best_phrase, sim = None, 0.0
                        else:
                            if best_phrase is not None and sim >= (
                                (best_phrase.threshold_pct or 80) / 100.0
                            ):
                                settings = await asyncio.to_thread(_get_settings, sid)
                                cooldown_sec = int(settings.get("cooldown_sec", 5))
                                alert_enabled = bool(settings.get("alert_enabled", True))
                                kw_phrase = f"phrase:{best_phrase.custom_phrase_id}"
                                if not _is_in_cooldown(
                                    sid, kw_phrase, best_phrase.event_type, cooldown_sec, ts_ms
                                ):
                                    text_phrase = (
                                        f"CustomPhraseAudio:{best_phrase.name} (sim={sim:.2f})"
                                    )
                                    _last_alert_ts_by_key[(sid, kw_phrase, best_phrase.event_type)] = ts_ms
                                    entry_p = memory_logs.append_alert(
                                        sid,
                                        text_phrase,
                                        kw_phrase,
                                        best_phrase.event_type,
                                        "warning",
                                        float(sim),
                                        ts_ms=ts_ms,
                                        source="custom_phrase",
                                    )
                                    event_id = await asyncio.to_thread(
                                        _persist_alert,
                                        sid,
                                        text_phrase,
                                        kw_phrase,
                                        best_phrase.event_type,
                                        ts_ms,
                                    )
                                    if event_id is not None:
                                        entry_p["event_id"] = event_id
                                    if alert_enabled:
                                        await manager.broadcast_to_session(sid, entry_p)
                                        audio_logger.info(
                                            "%s PHRASE_ALERT_EMITTED sid=%s phrase_id=%s sim=%.2f",
                                            conn_prefix,
                                            sid,
                                            best_phrase.custom_phrase_id,
                                            sim,
                                        )

                        # STT 큐에 넣어 단일 워커가 직렬 처리 (동시 다중 Whisper 방지)
                        item = {
                            "sid": sid,
                            "speech_audio": speech_audio,
                            "ts_ms": ts_ms,
                            "conn_prefix": conn_prefix,
                            "websocket": websocket,
                        }
                        try:
                            STT_QUEUE.put_nowait(item)
                            inc("stt_enqueued")
                        except asyncio.QueueFull:
                            inc("stt_dropped")
                            audio_logger.warning(
                                "%s STT_QUEUE_FULL sid=%s", conn_prefix, sid
                            )
            if "start" in vad_ev and not st.in_speech:
                st.in_speech = True
                st.speech_chunks = []  # 아래 append에서 현재 청크 추가
                audio_logger.info(
                    "VAD_START session_id=%s ts_ms=%s start=%s",
                    sid, ts_ms, vad_ev.get("start"),
                )
            if "end" not in vad_ev and "start" not in vad_ev:
                audio_logger.debug("VAD_EVT session_id=%s ev=%s", sid, vad_ev)
        if st.in_speech:
            st.speech_chunks.append(audio_f32.copy())
        else:
            # 비말(non-speech) 구간: 0.5초 청크 2개 모이면 1초 윈도우로 큐에 넣기
            st.non_speech_chunks.append(audio_f32.copy())
            if len(st.non_speech_chunks) >= 2:
                win = np.concatenate(st.non_speech_chunks[:2])
                st.non_speech_chunks = st.non_speech_chunks[1:]  # 슬라이딩(0.5초 겹침)
                settings = await asyncio.to_thread(_get_settings, sid)
                item = {
                    "sid": sid,
                    "ts_ms": ts_ms,
                    "audio": win,
                    "conn_prefix": conn_prefix,
                    "cooldown_sec": int(settings.get("cooldown_sec", 5)),
                    "alert_enabled": bool(settings.get("alert_enabled", True)),
                }
                try:
                    AUDIOCLS_QUEUE.put_nowait(item)
                    inc("yamnet_enqueued")
                except asyncio.QueueFull:
                    inc("yamnet_dropped")
                    audio_logger.warning(
                        "%s AUDIOCLS_QUEUE_FULL sid=%s", conn_prefix, sid
                    )
        return sid

    if msg_type == "caption":
        sid = msg.get("session_id")
        text = msg.get("text", "")
        if not sid:
            return session_id
        new_sid = session_id if session_id else sid
        if session_id is None:
            await manager.connect(websocket, sid)
        logger.debug(f"{conn_prefix}ws_caption_received session_id={sid} text_len={len(text)}")
        ts_ms = msg.get("ts_ms") or int(time.time() * 1000)
        await _handle_caption_generated(
            websocket=websocket,
            sid=sid,
            text=text,
            ts_ms=ts_ms,
            conn_prefix=conn_prefix,
        )
        return new_sid

    if msg_type == "send_caption":
        # 클라이언트 타이핑 자막: 같은 세션에 브로드캐스트 (입력한 사람 포함 표시)
        sid = msg.get("session_id") or session_id
        text = (msg.get("text") or "").strip()
        if not sid:
            logger.warning(f"{conn_prefix}send_caption ignored no session_id")
            return session_id
        if not text:
            return session_id
        ts_ms = msg.get("ts_ms") or int(time.time() * 1000)
        logger.info(f"{conn_prefix}send_caption session_id={sid} text_len={len(text)} text={text[:40]!r}")
        await _handle_caption_generated(
            websocket=websocket,
            sid=sid,
            text=text,
            ts_ms=ts_ms,
            conn_prefix=conn_prefix,
        )
        return sid

    if session_id is None and msg.get("session_id"):
        return msg["session_id"]

    return session_id
