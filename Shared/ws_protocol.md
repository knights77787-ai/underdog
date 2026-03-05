# WebSocket 메시지 규격 (프로토콜)

> **이 문서가 뭔가요?**  
> 클라이언트(브라우저/앱)가 **WebSocket**으로 서버에 접속한 뒤, 서버와 주고받는 **JSON 메시지 종류와 형식**을 정리한 겁니다.  
> "누가 누구에게 보내는지", "각 필드가 뭔지"만 보면 됩니다.

---

## 시연용 핵심 요약

- **WS URL:** `ws://host/ws`
- **연결 흐름:** connect → **join** `{ "type": "join", "session_id": "S1" }` → **join_ack**
- **수신 메시지:**  
  - **caption** — Whisper(STT) 결과(자막)  
  - **alert** — 키워드/환경음/데모 알림 (`keyword`, `event_type`, `source` 등)
- **alert.source:** `"text"`(또는 없음, 키워드 감지), `"audio"`(YAMNet 환경음), `"custom_phrase"`(Whisper 커스텀 구문), `"demo"`(데모 트리거)

---

## 연결 흐름 요약

1. 클라이언트가 WebSocket URL로 **연결**  
2. 서버가 **hello** 한 번 보냄 → "연결됐어요"  
3. 클라이언트가 **join** 보냄 → "이 방(세션)에 들어갈게요"  
4. 서버가 **join_ack** 보냄 → "들어왔어요, 이게 세션 ID예요"  
5. 이후 서버가 **caption** / **alert** 를 같은 세션 사람들에게 **브로드캐스트** (실시간 자막·알림)

---

## hello (서버 → 클라이언트)

**언제:** WebSocket 연결이 맺어진 직후, **서버가 한 번** 보냅니다.  
**의미:** "연결 수락했어요. 이제 메시지 주고받을 수 있어요."

```json
{"type": "hello"}
```

| 필드 | 의미 |
|------|------|
| `type` | 메시지 종류. `"hello"`면 연결 환영 메시지 |

---

## join (클라이언트 → 서버)

**언제:** 클라이언트가 "이 세션(방)에 참가하겠다"고 할 때 보냅니다.  
**의미:** "이 `session_id`(방) 로그/알림을 받고 싶어요."  
(문서에 예시가 없어도, 실제 구현에서는 클라이언트가 `{"type": "join", "session_id": "sess-abc"}` 형태로 보냅니다.)

---

## audio_chunk (클라이언트 → 서버)

**언제:** 클라이언트가 실시간 음성 스트림을 서버로 보낼 때, 청크 단위로 보냅니다.  
**의미:** "이 세션의 이 시각 오디오 청크예요." 서버는 VAD/STT 파이프라인에서 사용합니다.

```json
{
  "type": "audio_chunk",
  "session_id": "S1",
  "ts_ms": 1772174179834,
  "sr": 16000,
  "format": "pcm_s16le",
  "data_b64": "..."
}
```

| 필드 | 의미 |
|------|------|
| `type` | 메시지 종류. `"audio_chunk"` |
| `session_id` | 오디오 세션 ID (예: "S1") |
| `ts_ms` | 타임스탬프(밀리초). long |
| `sr` | 샘플레이트. **고정 16000** |
| `format` | 오디오 포맷. **고정 `pcm_s16le`** (16bit signed little-endian PCM) |
| `data_b64` | **base64 인코딩된 int16 PCM raw bytes** |

**프론트 권장: 0.5초 청크 규칙**  
- 포맷: 16kHz mono PCM int16  
- 0.5초 = 8000 samples = 16000 bytes (raw) → base64 인코딩 후 `data_b64`에 담아 전송  
- 청크를 일정하게 보내면 VAD/STT 처리가 안정적임

---

## join_ack (서버 → 클라이언트)

**언제:** 클라이언트가 **join** 을 보낸 뒤, 서버가 응답으로 보냅니다.  
**의미:** "해당 세션에 들어갔어요. 앞으로 이 `session_id` 로 caption/alert 를 받을 수 있어요."

```json
{"type": "join_ack", "session_id": "sess-abc"}
```

| 필드 | 의미 |
|------|------|
| `type` | 메시지 종류. `"join_ack"` = join 수락 확인 |
| `session_id` | 실제로 들어간 세션(방) ID. 이후 오는 caption/alert 의 `session_id` 와 같음 |

---

## caption (서버 → 클라이언트, 같은 세션 브로드캐스트)

**언제:** STT(음성→글) 결과나 자막이 나올 때, **해당 세션에 join 한 클라이언트들에게만** 서버가 보냅니다.  
**의미:** "이 방에서 이 시각에 이 자막이 나왔어요."

```json
{
  "type": "caption",
  "session_id": "sess-abc",
  "text": "안녕하세요",
  "ts_ms": 1730123456789
}
```

| 필드 | 의미 |
|------|------|
| `type` | 메시지 종류. `"caption"` = 자막/STT 한 건 |
| `session_id` | 어떤 세션(방)에서 발생했는지. join 할 때 썼던 ID |
| `text` | 자막/인식된 문장 내용 |
| `ts_ms` | 해당 구간(또는 이벤트)의 시각. 밀리초 타임스탬프 (로그/재생 동기화용) |

---

## alert (서버 → 클라이언트, 같은 세션 브로드캐스트)

**언제:** 키워드·위험 감지 등으로 **알림**이 발생했을 때, 해당 세션에 join 한 클라이언트들에게 서버가 보냅니다.  
**판정 우선순위:** warning(경고) 키워드 우선 → daily(일상) 키워드. **키워드 없으면 alert 이벤트는 저장하지 않음**(caption(pass)만 남음).  
**설정 반영:** 세션 설정의 `alert_enabled`가 False면 알림은 DB에만 저장하고 브로드캐스트는 하지 않음. `cooldown_sec` 동안 같은 (세션, keyword, event_type) 알림은 한 번만 저장·발행.

```json
{
  "type": "alert",
  "category": "warning",
  "event_type": "danger",
  "keyword": "불",
  "text": "불이야 도와줘",
  "session_id": "S1",
  "ts_ms": 1772174179036,
  "score": 1.0
}
```

| 필드 | 의미 |
|------|------|
| `type` | 메시지 종류. `"alert"` = 알림 한 건 |
| `source` | (선택) `"text"`(키워드, 또는 없음), `"audio"`(YAMNet 환경음), `"demo"`(데모 트리거) |
| `category` | `"warning"`(경고) 또는 `"daily"`(일상). daily/warning 구분용 |
| `event_type` | `"danger"`(경고), `"alert"`(일상 알림), `"info"`(저장만, WS에는 안 나옴) |
| `keyword` | 감지된 키워드 (예: "불", "비상", "yamnet:Siren", "demo:demo") |
| `text` | 알림과 함께 내려주는 문장 (예: TTS용) |
| `session_id` | 어떤 세션에서 발생했는지 |
| `ts_ms` | 알림 발생 시각(ms) |
| `score` | 판정 점수 (예: 1.0=경고, 0.7=일상, 0.2=info) |

---

## 정리 표

| 메시지 타입 | 방향 | 언제 쓰나 |
|-------------|------|-----------|
| **hello** | 서버 → 클라이언트 | 연결 직후, 한 번 |
| **join** | 클라이언트 → 서버 | 특정 세션(방) 참가 요청 |
| **audio_chunk** | 클라이언트 → 서버 | 실시간 오디오 청크 (16kHz PCM S16LE, base64) |
| **join_ack** | 서버 → 클라이언트 | join 수락 후, 세션 ID 확인 |
| **caption** | 서버 → 클라이언트 | 자막/STT 한 건 (같은 세션 브로드캐스트) |
| **alert** | 서버 → 클라이언트 | 알림 한 건 (같은 세션 브로드캐스트) |

**브로드캐스트:** 같은 `session_id` 로 join 한 모든 클라이언트에게 동시에 보내는 것.  
즉, caption/alert 는 "그 방에 있는 사람만" 받습니다.
