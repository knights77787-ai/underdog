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

**정리:**  
- **GET /logs** → 로그 목록 조회 (스크롤: `until_ts_ms` + `next_until_ts_ms`, `has_more`)  
- **GET /admin/summary** → 관리자 요약 (개수, 최근 알림, 마지막 이벤트)  
- **POST /feedback** → 이벤트별 좋아요/싫어요·코멘트 저장  
- **GET /settings** → 세션별 설정 조회 (없으면 기본값 생성)  
- **POST /settings** → 세션별 설정 일부 merge 저장  
