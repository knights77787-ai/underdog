# REST API 응답 규격

> **이 문서가 뭔가요?**  
> 프론트엔드가 백엔드 REST API를 호출할 때, "어떤 URL에 어떤 값을 보내면, 어떤 JSON이 돌아오는지"를 정리한 계약서입니다.  
> 여기 적힌 필드명·타입·예시를 기준으로 프론트/백이 맞춰 개발합니다.

---

## GET /logs

**역할:** 실시간 자막·알림 로그를 "목록"으로 조회하는 API입니다.  
**페이지네이션 대신 "스크롤로 더 불러오기"** 방식을 쓰므로, 커서(`until_ts_ms`)로 이어서 조회합니다.

### 쿼리 파라미터 (URL 뒤에 붙는 값)

| 파라미터      | 의미 | 예시 |
|--------------|------|------|
| `type`       | 가져올 로그 종류. `all`=전부, `caption`=자막만, `alert`=알림만 | `type=all` |
| `limit`      | 한 번에 몇 건까지 가져올지 (숫자) | `limit=50` |
| `session_id` | 특정 세션(방) 로그만 볼 때. 없으면 전체 | `session_id=sess-abc` |
| `since_ts_ms`| 이 시간(ms) **이후** 로그만 (선택) | `since_ts_ms=1730123400000` |
| `until_ts_ms`| 이 시간(ms) **이하** 로그만. **스크롤 "더 불러오기"할 때 커서로 사용** | `until_ts_ms=1730123456789` |

### 사용 시나리오

- **첫 로딩:**  
  `GET /logs?type=all&session_id=S1&limit=50`  
  → "가장 최신 로그 50건"을 가져옵니다. `until_ts_ms` 없이 부르면 "현재 기준 최신"부터입니다.

- **스크롤로 더 불러오기 (과거로):**  
  `GET /logs?type=all&session_id=S1&limit=50&until_ts_ms=1772174179000`  
  → "그보다 과거 로그 50건"을 가져옵니다.  
  → 여기 넣는 `until_ts_ms`는 **직전 응답에 있던 `next_until_ts_ms`** 값을 그대로 쓰면 됩니다.

### 응답 예시 (서버가 돌려주는 JSON)

```json
{
  "ok": true,
  "type": "all",
  "session_id": null,
  "limit": 100,
  "count": 2,
  "data": [
    {
      "type": "alert",
      "event_type": "danger",
      "keyword": "비상",
      "session_id": "sess-abc",
      "text": "비상 상황입니다",
      "ts_ms": 1730123456790
    },
    {
      "type": "caption",
      "session_id": "sess-abc",
      "text": "안녕하세요",
      "ts_ms": 1730123456789
    }
  ],
  "next_until_ts_ms": 1730123456789,
  "has_more": true
}
```

### 응답 필드 설명

| 필드 | 의미 |
|------|------|
| `ok` | 요청 처리 성공 여부. `true`면 정상 |
| `type` | 요청할 때 보낸 `type` 그대로 (all/caption/alert) |
| `session_id` | 요청할 때 보낸 `session_id` (없으면 null) |
| `limit` | 요청할 때 보낸 `limit` (최대치로 잘린 값) |
| `count` | 이번에 실제로 내려준 로그 개수 (`data` 배열 길이) |
| `data` | 로그 항목 배열. **최신이 위(앞), 과거가 아래(뒤)** 순서 |
| `next_until_ts_ms` | 이번에 준 데이터 중 **가장 과거 항목의 `ts_ms`**. 다음 "더 불러오기" 요청 시 `until_ts_ms`에 이 값을 넣으면 됨 |
| `has_more` | `true`면 "그보다 과거 로그가 더 있다"는 뜻. 스크롤 끝에서 한 번 더 요청해도 됨 |

### `data` 안 각 항목 공통

- `type`: `"caption"`(자막) 또는 `"alert"`(알림)
- `session_id`: 어떤 세션(방)에서 발생했는지
- `text`: 자막/알림 문장
- `ts_ms`: 발생 시각 (밀리초 타임스탬프)

알림(`type: "alert"`)일 때만 추가로:

- `event_type`: `"danger"` 또는 `"alert"`
- `keyword`: 감지된 키워드 (예: "비상")

---

## GET /admin/alerts

**역할:** 관리자용 **알림(alert) 로그만** 목록 조회.  
**페이지네이션은 `/logs`와 동일하게 "스크롤로 더 불러오기"** 방식이며, 커서(`until_ts_ms`)로 이어서 조회합니다.

### 쿼리 파라미터

| 파라미터      | 의미 | 예시 |
|--------------|------|------|
| `limit`      | 한 번에 몇 건까지 가져올지 (1~500, 추천 50~100) | `limit=50` |
| `session_id` | 특정 세션 알림만 볼 때 (선택). 없으면 전체 | `session_id=S1` |
| `since_ts_ms`| 이 시간(ms) **이후** 알림만 (선택) | 생략 가능 |
| `until_ts_ms`| **커서(과거로 더 불러올 기준).** 이 값보다 **이전(더 과거)** 알림을 가져옴. 첫 로딩 시 생략 | `until_ts_ms=1772174178123` |

### 사용 시나리오

- **첫 로딩 (최신 N개):**  
  `GET /admin/alerts?limit=50` 또는 `GET /admin/alerts?session_id=S1&limit=50`  
  → 응답의 `data`를 그대로 화면에 렌더링하고, **`next_until_ts_ms`를 저장**합니다.

- **스크롤로 "더 불러오기" (과거 알림 이어붙이기):**  
  `GET /admin/alerts?limit=50&until_ts_ms=<next_until_ts_ms - 1>`  
  → 다음 요청에는 **`until_ts_ms = next_until_ts_ms - 1`** 로 보냅니다.  
  (같은 `ts_ms`가 여러 개일 때 중복으로 다시 오는 걸 막기 위함)  
  → 응답의 `data`를 기존 리스트 **뒤(아래)**에 append 하고, `next_until_ts_ms`를 새 값으로 업데이트합니다.  
  → **`has_more === false`** 이면 더 이상 요청하지 않습니다.

### 응답 필드

| 필드 | 의미 |
|------|------|
| `ok` | 요청 처리 성공 여부 |
| `limit` | 요청 시 보낸 `limit` |
| `count` | 이번에 내려준 알림 개수 (`data` 길이) |
| `data` | 알림 배열. **최신 → 과거** 순서 |
| `next_until_ts_ms` | 다음 요청에 넣을 커서 값 (이번 배치 중 가장 과거 항목의 `ts_ms`) |
| `has_more` | 더 가져올 알림이 있는지 (boolean) |

### 응답 예시

```json
{
  "ok": true,
  "limit": 50,
  "count": 50,
  "data": [
    {
      "type": "alert",
      "event_id": 102,
      "event_type": "danger",
      "keyword": "불",
      "session_id": "S1",
      "text": "비상 상황입니다",
      "ts_ms": 1772174179036
    }
  ],
  "next_until_ts_ms": 1772174178123,
  "has_more": true
}
```

### 무한 스크롤 규칙 (필수)

1. **중복 방지:** 다음 요청에서 `until_ts_ms = next_until_ts_ms - 1` 로 보낸다. (동일 `ts_ms` 복수 건 시 중복 방지)
2. **추가 위치:** 응답의 `data`는 기존 리스트 **뒤(아래)**에 append 한다.
3. **커서 갱신:** `next_until_ts_ms`를 응답의 새 값으로 업데이트한다.
4. **종료 조건:** `has_more === false` 이면 더 이상 요청하지 않는다.

### 프론트 구현 팁 (필수)

- **로딩 잠금:** 동시에 여러 번 호출하지 않도록 `isLoading` 플래그로 잠근다.
- **스크롤 종료:** 서버 응답이 비어 있거나 `has_more === false` 이면 스크롤 로딩을 종료한다.
- **리스트 key:** 알림 항목에는 `event_id`(있으면) 또는 `(ts_ms, event_type)` 조합을 key로 사용한다.

---

## GET /admin/summary

**역할:** 관리자용 "대시보드 요약"입니다.  
전체/특정 세션의 자막·알림 개수, 최근 알림 개수, 마지막 이벤트 한 건 등을 한 번에 줍니다.

### 쿼리 파라미터

| 파라미터 | 의미 | 예시 |
|----------|------|------|
| `session_id` | 특정 세션만 집계. 없으면 전체 | `session_id=sess-abc` |
| `since_ts_ms` | 이 시간(ms) 이후만 집계 (선택) | 생략 가능 |
| `until_ts_ms` | 이 시간(ms) 이하만 집계 (선택) | 생략 가능 |
| `recent_window_sec` | "최근 N초" 알림 개수 셀 때 구간(초). 기본 300(5분) | `recent_window_sec=60` |

### 응답 예시

```json
{
  "ok": true,
  "summary": {
    "session_id": null,
    "total_captions": 10,
    "total_alerts": 2,
    "alerts_recent": {
      "window_sec": 300,
      "count": 1,
      "since_ts_ms": 1730123300000
    },
    "unique_sessions": 1,
    "session_ids": ["sess-abc"],
    "last_event_ts_ms": 1730123456790,
    "last_event": {
      "type": "alert",
      "event_type": "danger",
      "keyword": "비상",
      "session_id": "sess-abc",
      "text": "비상 상황입니다",
      "ts_ms": 1730123456790
    }
  }
}
```

### `summary` 필드 설명

| 필드 | 의미 |
|------|------|
| `session_id` | 요청 시 넣은 `session_id` (없으면 null) |
| `total_captions` | 조건에 맞는 자막 이벤트 총 개수 |
| `total_alerts` | 조건에 맞는 알림 이벤트 총 개수 |
| `alerts_recent` | "최근 N초" 안에 발생한 알림 정보 |
| ↳ `window_sec` | 그 N초 (기본 300) |
| ↳ `count` | 그 구간 안 알림 개수 |
| ↳ `since_ts_ms` | 그 구간의 시작 시각(ms) |
| `unique_sessions` | 조건에 맞는 서로 다른 세션 개수 |
| `session_ids` | 세션 ID 목록 (예: 대시보드에 표시용) |
| `last_event_ts_ms` | 가장 마지막(최신) 이벤트의 시각(ms) |
| `last_event` | 가장 마지막 이벤트 한 건 (구조는 `/logs`의 `data` 항목과 동일) |

---

## POST /feedback

**역할:** 특정 이벤트(자막/알림)에 대해 사용자가 "좋아요/싫어요"나 코멘트를 남기는 API입니다.  
DB에 저장되고, 같은 이벤트에 대해 세션당 1회만 허용(같은 세션이 다시 보내면 기존 걸 업데이트).

### 요청 (Request Body, JSON)

| 필드 | 필수 | 의미 |
|------|------|------|
| `event_id` | ✅ | 피드백을 달 이벤트 ID (숫자). `/logs`의 이벤트나 WebSocket으로 받은 이벤트와 매칭 |
| `vote` | ✅ | `"up"` 또는 `"down"` (좋아요/싫어요) |
| `comment` | ❌ | 자유 텍스트 코멘트 (선택) |
| `client_session_uuid` | ❌ | 클라이언트 세션 식별자. 있으면 "이 세션당 1건" 정책에 사용 |

### 요청 예시

```json
{
  "event_id": 1,
  "vote": "up",
  "comment": "정확해요",
  "client_session_uuid": "sess-abc"
}
```

### 응답 예시

```json
{
  "ok": true,
  "feedback_id": 1,
  "event_id": 1,
  "vote": "up",
  "comment": "정확해요"
}
```

### 응답 필드 설명

| 필드 | 의미 |
|------|------|
| `ok` | 저장 성공 여부 |
| `feedback_id` | DB에 저장된 피드백 고유 ID |
| `event_id` | 요청에서 보낸 이벤트 ID |
| `vote` | 저장된 투표 값 (up/down) |
| `comment` | 저장된 코멘트. 없으면 `""` (빈 문자열) |

---

## GET /settings

**역할:** 해당 세션의 설정 조회. 없으면 기본값으로 한 건 생성 후 반환.

### 쿼리 파라미터

| 파라미터 | 필수 | 의미 |
|----------|------|------|
| `session_id` | ✅ | 클라이언트 세션 문자열 (예: S1, 또는 프론트에서 쓰는 UUID). DB의 `client_session_uuid`와 동일 |

### 응답 예시

```json
{
  "ok": true,
  "session_id": "S1",
  "data": {
    "font_size": 20,
    "alert_enabled": true,
    "cooldown_sec": 5,
    "auto_scroll": true
  }
}
```

---

## POST /settings

**역할:** 해당 세션 설정을 일부만 보내면 기존 값에 merge해서 저장. (없으면 기본값 기준으로 생성 후 merge)

### 쿼리 파라미터

| 파라미터 | 필수 | 의미 |
|----------|------|------|
| `session_id` | ✅ | GET /settings와 동일 (클라이언트 세션 문자열) |

### 요청 Body (JSON, 전부 선택)

| 필드 | 타입 | 검증 | 의미 |
|------|------|------|------|
| `font_size` | int | 10~60 | 글자 크기 |
| `alert_enabled` | bool | - | 알림 사용 여부 |
| `cooldown_sec` | int | 0~60 | 쿨다운(초) |
| `auto_scroll` | bool | - | 자동 스크롤 여부 |

보내지 않은 키는 기존 값 유지. `null`이 아닌 값만 보내면 됨.

### 요청 예시

```json
{
  "font_size": 24,
  "auto_scroll": false
}
```

### 응답 예시

```json
{
  "ok": true,
  "session_id": "S1",
  "data": {
    "font_size": 24,
    "alert_enabled": true,
    "cooldown_sec": 5,
    "auto_scroll": false
  }
}
```

---

---

## POST /auth/guest

**역할:** 로그인 없이 바로 사용할 수 있는 **게스트 세션**을 하나 만들고, 그 세션을 식별하는 `session_id`를 내려줍니다.  
이 `session_id`는 WebSocket `join.session_id`, `/logs`, `/settings` 등에서 쓰는 값과 동일합니다.

### 요청

- 메서드: `POST`
- 경로: `/auth/guest`
- 바디: 없음

### 응답 예시

```json
{
  "ok": true,
  "session_id": "6b4c9b8e-3a7f-4f2d-bc1d-1a2b3c4d5e6f",
  "user": {
    "id": null,
    "name": null,
    "email": null,
    "provider": "guest"
  }
}
```

### 필드 설명

| 필드 | 의미 |
|------|------|
| `ok` | 성공 여부 |
| `session_id` | 새로 생성된 게스트 세션의 식별자 (UUID 문자열). WebSocket `join.session_id` 및 `/logs`, `/settings` 쿼리의 `session_id`로 그대로 사용 |
| `user.id` | 게스트는 별도 User 레코드를 만들지 않으므로 항상 `null` |
| `user.name` | 게스트이므로 `null` |
| `user.email` | 게스트이므로 `null` |
| `user.provider` | `"guest"` 고정 |

---

## GET /auth/google/login

**역할:** 구글 로그인 화면으로 리다이렉트하는 엔드포인트입니다.  
프론트에서 `window.location` 또는 새 창으로 이 URL을 열면, 사용자는 구글 로그인/동의 화면으로 이동합니다.

- 메서드: `GET`
- 경로: `/auth/google/login`
- 쿼리/바디: 없음
- 응답: **302 Redirect** → Google OAuth 동의 화면

> 서버 환경변수: `GOOGLE_CLIENT_ID`, `GOOGLE_REDIRECT_URI`, `GOOGLE_CLIENT_SECRET` 이 설정되어 있어야 합니다.

---

## GET /auth/google/callback

**역할:** 구글에서 `code`를 들고 되돌아오는 콜백 URL입니다.  
서버가 이 `code`로 access_token을 교환하고, 사용자 정보를 조회한 뒤, 내부적으로 User/Session을 생성하고 **프론트 페이지로 다시 리다이렉트**합니다.

- 메서드: `GET`
- 경로: `/auth/google/callback`

### 쿼리 파라미터

| 파라미터 | 의미 |
|----------|------|
| `code` | 구글이 넘겨주는 OAuth authorization code |

### 동작 요약

1. 서버가 `code`를 사용해 Google 토큰 엔드포인트에 요청 → `access_token` 획득
2. `access_token`으로 Google 사용자 정보 조회 (`sub`, `email`, `name` 등)
3. DB `users` 테이블에서 `(oauth_provider="google", oauth_sub=sub)`로 사용자 조회, 없으면 생성
4. DB `sessions` 테이블에 `is_guest=false`, `user_id=<위 사용자 PK>`, `client_session_uuid=<새 UUID>` 인 세션 하나 생성
5. 환경변수 `FRONTEND_AUTH_REDIRECT_URL` (기본값 `/`) 로 **302 Redirect** 응답
   - 리다이렉트 URL 예시: `/live?session_id=<client_session_uuid>&provider=google`

### 리다이렉트 URL 쿼리 예시

```text
/live?session_id=6b4c9b8e-3a7f-4f2d-bc1d-1a2b3c4d5e6f&provider=google
```

프론트에서는 이 URL에서 `session_id`를 파싱해:

- WebSocket `join` 시 `session_id` 필드로 사용
- `/logs`, `/settings`, `/custom-sounds`, `/custom-phrase-audio` 호출 시 `session_id` 쿼리로 사용하면 됩니다.

---

## GET /auth/kakao/login

**역할:** 카카오 로그인 화면으로 리다이렉트하는 엔드포인트입니다.

- 메서드: `GET`
- 경로: `/auth/kakao/login`
- 쿼리/바디: 없음
- 응답: **302 Redirect** → Kakao OAuth 동의 화면

> 서버 환경변수: `KAKAO_CLIENT_ID`, `KAKAO_REDIRECT_URI` (필수), `KAKAO_CLIENT_SECRET`(선택)이 설정되어 있어야 합니다.

---

## GET /auth/kakao/callback

**역할:** 카카오에서 `code`를 들고 되돌아오는 콜백 URL입니다.  
Google과 거의 동일한 흐름으로 User/Session을 만들고, 프론트 페이지로 리다이렉트합니다.

- 메서드: `GET`
- 경로: `/auth/kakao/callback`

### 쿼리 파라미터

| 파라미터 | 의미 |
|----------|------|
| `code` | 카카오가 넘겨주는 OAuth authorization code |

### 동작 요약

1. 서버가 `code`로 카카오 토큰 엔드포인트에 요청 → `access_token` 획득
2. `access_token`으로 `https://kapi.kakao.com/v2/user/me` 호출 → `id`, `kakao_account.email`, `profile.nickname` 등 조회
3. DB `users` 테이블에서 `(oauth_provider="kakao", oauth_sub=str(id))`로 사용자 조회, 없으면 생성
4. DB `sessions` 테이블에 `is_guest=false`, `user_id=<위 사용자 PK>`, `client_session_uuid=<새 UUID>` 인 세션 생성
5. `FRONTEND_AUTH_REDIRECT_URL`(기본 `/`) 기준으로 **302 Redirect**
   - 예시: `/live?session_id=<client_session_uuid>&provider=kakao`

---

## API 목록 (시연/팀 참고)

| 메서드 | 경로 | 비고 |
|--------|------|------|
| GET | `/logs` | 커서 방식: `until_ts_ms` = 직전 응답의 `next_until_ts_ms` |
| GET | `/admin/summary` | 요약 집계 |
| GET | `/admin/alerts` | 알림 목록 (스크롤 동일) |
| GET | `/admin/metrics` | 큐 크기·카운터·세션 수 |
| GET | `/admin/health` | DB·worker·큐·룰 종합 (시연 전 점검) |
| POST | `/admin/reload-keywords` | 키워드 룰 핫리로드 |
| POST | `/admin/reload-audio-rules` | 오디오 룰 핫리로드 |
| POST | `/feedback` | 이벤트별 좋아요/싫어요·코멘트 |
| GET | `/admin/feedback-summary` | 키워드별 up/down 집계 |
| GET | `/admin/feedback-suspects` | 오탐 의심 키워드 후보 |
| POST | `/admin/demo/emit` | (데모) 한 번 눌러서 경고 이벤트 생성 |
| GET | `/settings` | 세션별 설정 조회 |
| POST | `/settings` | 세션별 설정 merge 저장 |
| POST | `/auth/guest` | 게스트 세션 생성 (`session_id` 발급) |
| GET | `/auth/google/login` | 구글 로그인 페이지로 리다이렉트 |
| GET | `/auth/google/callback` | 구글 OAuth 콜백 → 세션 생성 후 프론트로 리다이렉트 |
| GET | `/auth/kakao/login` | 카카오 로그인 페이지로 리다이렉트 |
| GET | `/auth/kakao/callback` | 카카오 OAuth 콜백 → 세션 생성 후 프론트로 리다이렉트 |
| POST | `/custom-sounds` | 커스텀 소리(YAMNet) 오디오 업로드·등록 (.wav, .mp3) |
| GET | `/custom-sounds` | 세션별 커스텀 소리 목록 조회 |
| POST | `/custom-phrase-audio` | 커스텀 구문(Whisper embedding) 오디오 업로드·등록 (.wav, .mp3) |
| GET | `/custom-phrase-audio` | 세션별 커스텀 구문 목록 조회 |

---

### POST /custom-sounds (커스텀 환경음 등록)

- **역할:** YAMNet embedding 기반 커스텀 소리(환경음) 등록. 실시간 비말 구간과 코사인 유사도로 매칭 후 alert 발생.
- **요청:** `session_id`(Query), `name`, `group_type`, `event_type`(Form), `file`(.wav 또는 .mp3, 1초 권장). MP3는 pydub·ffmpeg 필요.
- **응답:** `{"ok": true, "data": {"custom_sound_id": int, "name": str}}`

### GET /custom-sounds

- **쿼리:** `session_id` (필수)
- **응답:** `{"ok": true, "count": N, "data": [{"custom_sound_id", "name", "group_type", "event_type"}, ...]}`

### POST /custom-phrase-audio (커스텀 안내 음성 등록)

- **역할:** Whisper encoder embedding 기반 커스텀 구문(안내 방송 등) 등록. VAD_END 말 구간과 코사인 유사도로 매칭 후 alert 발생.
- **요청:** `session_id`(Query), `name`, `event_type`(Form, `alert`|`danger`), `threshold_pct`(Form, 50~99, 기본 80), `file`(.wav 또는 .mp3, 약 2초 권장).
- **응답:** `{"ok": true, "data": {"custom_phrase_id": int, "name": str}}`

### GET /custom-phrase-audio

- **쿼리:** `session_id` (필수)
- **응답:** `{"ok": true, "count": N, "data": [{"custom_phrase_id", "name", "event_type", "threshold_pct"}, ...]}`

---

## 시연 체크리스트 (강추)

1. **GET /admin/health** → `db_ok: true`, `tasks` alive(done: false)
2. **(말)** "불이야" 말하기 → caption + danger 알림
3. **(환경음)** 사이렌 재생 → audio alert
4. **GET /admin/alerts** 에서 2건 이상 확인
5. 피드백 저장 (POST /feedback)
6. **GET /admin/feedback-suspects** 확인
7. 쿨/룰 수정 후 reload (reload-keywords / reload-audio-rules)
8. 다시 재생해서 분류 바뀐 것 확인
9. 문제 생기면 **POST /admin/demo/emit** 로 이벤트 띄우기
10. **GET /admin/metrics** 로 처리/드롭·평균 처리시간 확인

---

**정리:**  
- **GET /logs** → 로그 목록 조회 (스크롤: `until_ts_ms` + `next_until_ts_ms`, `has_more`)  
- **GET /admin/alerts** → 관리자 알림 목록 조회 (동일 스크롤 방식: `until_ts_ms`, `next_until_ts_ms`, `has_more`)  
- **GET /admin/summary** → 관리자 요약 (개수, 최근 알림, 마지막 이벤트)  
- **GET /admin/metrics**, **GET /admin/health** → 운영·시연 점검  
- **POST /admin/demo/emit** → 데모 트리거 (현장 소리 꼬여도 이벤트 발생)  
- **POST /feedback** → 이벤트별 좋아요/싫어요·코멘트 저장  
- **GET /admin/feedback-summary**, **GET /admin/feedback-suspects** → 피드백 집계·오탐 후보  
- **GET /settings** → 세션별 설정 조회 (없으면 기본값 생성)  
- **POST /settings** → 세션별 설정 일부 merge 저장  
