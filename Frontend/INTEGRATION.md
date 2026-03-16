# 프론트–백엔드 연동 가이드

백엔드는 만들어져 있고 프론트는 아직 연동이 안 된 상태에서, **지금 있는 프론트를 백엔드에 붙이는 방법**을 정리한 문서입니다.

---

## 1. 연동 전 체크

- **백엔드**: FastAPI, `http://127.0.0.1:8000` (또는 배포 URL)
- **WebSocket**: `ws://127.0.0.1:8000/ws`
- **프론트**: 정적 HTML/JS (Bootstrap), `index.html`(라이브), `new_sound.html`(커스텀 소리)

---

## 2. 라이브 화면 (index.html + live.js + wsClient.js)

### 2.1 반드시 할 것

| 항목 | 설명 |
|------|------|
| **WS 연결 후 join 전송** | 백엔드는 **join**을 받아야 해당 세션으로 caption/alert를 브로드캐스트합니다. 연결만 하고 join을 안 보내면 이벤트를 받지 못합니다. |
| **join 메시지 형식** | `{ "type": "join", "session_id": "S1" }` (또는 프론트에서 생성한 세션 ID) |
| **서버 필드명** | caption/alert 모두 **`ts_ms`** (밀리초 타임스탬프). `ts`가 아님. |

### 2.2 권장 흐름

1. `ws://host/ws` 연결
2. 서버에서 `{"type":"hello"}` 수신
3. **즉시** `{"type":"join","session_id":"S1"}` 전송 (S1 대신 고정값/쿼리/로컬스토리지 등 사용 가능)
4. 서버에서 `{"type":"join_ack","session_id":"S1"}` 수신 → 이후 해당 세션의 caption/alert 수신 가능
5. 수신 메시지: `type` = `caption` | `alert`, 표시 시 **`ts_ms`** 사용 (필요하면 `new Date(ts_ms).toLocaleTimeString()` 등으로 포맷)

### 2.3 참고

- **테스트용 자막 전송**: 현재 백엔드는 클라이언트가 보내는 `send_caption` 같은 타입을 처리하지 않습니다. 자막은 **마이크 → 오디오 청크(audio_chunk) → 서버 STT** 흐름으로만 생성됩니다. 테스트는 `POST /admin/demo/emit`으로 알림을 띄우거나, 실제로 말해서 확인하면 됩니다.
- **피드백(맞아요/아니에요)**: UI만 있는 상태면, **POST /feedback** 연동 시 `event_id`, `vote`("up"|"down"), `comment`(선택)를 보내면 됩니다. `event_id`는 alert 이벤트의 ID(로그 API 등에서 확인).

---

## 3. 커스텀 소리 등록 (new_sound.html + new_sound.js)

### 3.1 백엔드 API

- **URL**: `POST /custom-sounds` (prefix만, 루트가 아님)
- **쿼리**: `session_id` (필수, 예: `S1`)
- **Body (multipart/form-data)**:
  - `name`: 소리 이름 (필수)
  - `group_type`: `"warning"` | `"daily"`
  - `event_type`: `"danger"` | `"alert"`
  - `file`: WAV 파일 (필수, **.wav만 지원**)

### 3.2 프론트와의 차이

| 현재 프론트 (추정) | 백엔드 스펙 |
|-------------------|-------------|
| `POST /api/sounds` | `POST /custom-sounds?session_id=S1` |
| `sound_name`, `sound_category`, `audio_file` | `name`, `group_type`, `event_type`, `file` |
| 파일: webm/업로드 가능 | **.wav만 지원** |

### 3.3 연동 방법

1. **요청 URL**: `http://127.0.0.1:8000/custom-sounds?session_id=S1` (같은 호스트면 상대 경로 `/custom-sounds?session_id=S1` 가능)
2. **Form 필드명**: `name`, `group_type`, `event_type`, `file`
3. **파일**: 서버가 WAV만 받으므로,  
   - 업로드 시 **.wav 파일만 선택**하도록 하거나,  
   - 녹음은 브라우저에서 WAV로 저장하는 라이브러리 사용,  
   - 또는 백엔드에 webm→wav 변환을 추가하는 방식 중 하나 선택

응답 성공 시: `{"ok": true, "data": {"custom_sound_id": 1, "name": "..."}}`

### 3.4 실시간 감지 연동

등록한 커스텀 소리는 **같은 session_id**로 라이브에서 마이크를 켜면 실시간으로 인식됩니다.

- 마이크 오디오 → WebSocket `audio_chunk` → 서버 VAD → 비음성 구간 → YAMNet embedding
- DB의 해당 세션 커스텀 소리 embedding과 코사인 유사도 비교
- 유사도 ≥ 0.75 시 alert 브로드캐스트 → 실시간 자막·경고 표시

자세한 흐름: `Docs/CUSTOM_SOUND_FLOW.md` 참고.

---

## 4. 설정 (선택)

- **GET /settings?session_id=S1**: 세션 설정 조회 (없으면 기본값 생성 후 반환)
- **POST /settings?session_id=S1**: body에 `font_size`, `alert_enabled`, `cooldown_sec`, `auto_scroll` 등 일부만 보내서 merge

라이브 화면에서 세션 ID를 S1으로 쓴다면, 같은 `session_id`로 설정 API를 호출하면 됩니다.

---

## 5. 프론트 서빙 (백엔드에서 HTML/정적 파일 제공)

**Backend/App/main.py** 에서 프론트를 서빙합니다. 같은 오리진이므로 CORS 없이 동작합니다.

| 경로 | 설명 |
|------|------|
| `GET /` | 라이브 메인 (index.html) |
| `GET /login` | 로그인 페이지 (login.html) |
| `GET /live` | 라이브와 동일 (OAuth 콜백 리다이렉트용) |
| `GET /static/*` | Frontend/static (CSS, JS 등) |

- 프로젝트 구조가 `underdog/Frontend/`, `underdog/Backend/` 이어야 합니다. Backend에서 `uvicorn main:app` 실행 시 Frontend 폴더를 자동으로 찾습니다.
- **테스트 방법**은 **Frontend/TEST.md** 에 정리되어 있습니다.

## 6. CORS (다른 오리진에서 프론트 서빙할 때)

- 프론트를 **다른 포트/도메인**에서 서빙하면 CORS가 필요합니다. FastAPI에 `CORSMiddleware` 추가 여부 확인.
- 위처럼 **백엔드에서 같은 오리진으로** HTML/정적 파일을 주면 CORS 없이 동작합니다.

---

## 7. 요약 체크리스트

- [ ] **라이브**: WS 연결 후 **join** 전송 (`type`, `session_id`)
- [ ] **라이브**: caption/alert 표시 시 **ts_ms** 사용
- [ ] **커스텀 소리**: `POST /custom-sounds?session_id=...`, Form 필드 `name`, `group_type`, `event_type`, `file` (.wav)
- [ ] (선택) 피드백: **POST /feedback** with `event_id`, `vote`, `comment`
- [ ] (선택) 설정: **GET/POST /settings?session_id=...**

위만 맞추면 “지금 만들어진 백엔드”와 현재 프론트를 최소한으로 연동할 수 있습니다.
