# 남은 프론트 작업 단계별 가이드

오늘 안에 끝낼 수 있도록 **우선순위 순**으로 정리했습니다.

---

## ✅ 이미 적용된 것 (방금 반영)

- **POST /custom-sounds**  
  `new_sound.js`: 제출 시 `FormData`로 `name`, `group_type`, `event_type`, `file` 전송.  
  세션은 URL `session_id` 또는 기본 `S1`.  
  서버는 **.wav, .mp3**만 허용 → 프론트에서 .webm 선택 시 "등록은 .wav, .mp3만 지원합니다" 안내.

- **GET /custom-sounds**  
  "내가 등록한 소리 목록" 탭에서 `loadSoundList()` 호출 → 목록 렌더링.  
  탭 전환 시·등록 성공 후 자동 갱신.

---

## 1. GET /logs (라이브 페이지 – 로그 목록 + 더 불러오기)

**목표:** 라이브 페이지에서 과거 로그를 API로 불러와 테이블에 채우고, 스크롤/버튼으로 "더 불러오기".

**참고:** `Shared/api_contract.md` – GET /logs (쿼리: `type`, `limit`, `session_id`, `until_ts_ms`).

### 1-1. 상태 변수 추가 (live.js 상단 근처)

```js
let logsNextUntilTs = null;  // 다음 "더 불러오기" 시 사용할 커서
let logsHasMore = true;
let logsLoading = false;
const LOGS_LIMIT = 50;
```

### 1-2. 로그 한 배치 가져오기

```js
async function fetchLogs(append) {
  if (!SESSION_ID || logsLoading) return;
  logsLoading = true;
  const url = new URL(API_BASE + "/logs");
  url.searchParams.set("type", "all");
  url.searchParams.set("session_id", SESSION_ID);
  url.searchParams.set("limit", LOGS_LIMIT);
  if (append && logsNextUntilTs != null) url.searchParams.set("until_ts_ms", logsNextUntilTs);

  try {
    const res = await fetch(url);
    const data = await res.json().catch(() => ({}));
    if (!data.ok || !Array.isArray(data.data)) return;
    const list = data.data;
    logsNextUntilTs = data.next_until_ts_ms ?? null;
    logsHasMore = data.has_more === true;

    if (append) {
      list.forEach((item) => appendLogRowFromApi(item));
    } else {
      list.forEach((item) => appendLogRowFromApi(item)); // 첫 로딩은 기존 logTbody 비우고 위에서부터 채우거나, 기존 prepend 로직과 맞춰서 처리
    }
  } finally {
    logsLoading = false;
  }
}
```

- **첫 로딩:** `append === false` → `until_ts_ms` 없이 호출.  
  `logTbody.innerHTML = ""` 후, 응답 `data`는 **최신이 앞**이므로 `data.forEach(item => appendLogRowFromApi(item))`로 **순서대로 appendChild** 하면 화면에 최신이 위로 나옵니다.
- **더 불러오기:** `append === true` → `until_ts_ms = logsNextUntilTs`로 호출.  
  새로 받은 `data`는 더 과거 로그이므로 **테이블 맨 아래에 append** (같이 `appendChild`).

### 1-3. API 항목 → 테이블 행

`appendLogRow()`와 같은 형태로 `appendLogRowFromApi(item)` 구현.  
`item` 필드: `type`, `text`, `ts_ms`, `event_type`, `keyword` 등 (api_contract 참고).

### 1-4. 언제 호출할지

- **Connect 성공 직후:** `fetchLogs(false)` (첫 로딩).
- **"과거 로그 더 불러오기" 버튼:** `fetchLogs(true)`.  
  `index.html` 로그 카드 footer에 버튼 추가:

```html
<button id="btnLoadMoreLogs" type="button" class="btn btn-sm btn-outline-secondary">과거 로그 더 불러오기</button>
```

- `logsHasMore === false`이면 버튼 비활성화 또는 숨김.

### 1-5. 주의

- 첫 로딩 시 기존 `logTbody`를 `innerHTML = ""` 등으로 비울지, 실시간 WS 로그와 합칠지 결정.  
  합친다면: 첫 로딩은 "과거"만 API로 채우고, 실시간은 계속 `prepend` 유지.

---

## 2. 관리자 페이지 뼈대 (admin.html + admin.js)

**목표:** `/admin`에서 summary, health, 데모 emit, reload 버튼만 먼저 연동.

### 2-1. 라우트 확인

백엔드에 `GET /admin` 같은 HTML 서빙이 있으면 그대로, 없으면 Flask/FastAPI에서 `admin.html`을 서빙하는 라우트 추가 (예: `GET /admin` → `admin.html`).

### 2-2. admin.html 골격

- Bootstrap 포함 (다른 페이지와 동일).
- 영역 구분:
  - **요약:** GET /admin/summary → total_captions, total_alerts, alerts_recent, last_event 등 표시.
  - **헬스:** GET /admin/health → db_ok, tasks 등 표시.
  - **데모:** 버튼 "데모 알림 1건 발생" → POST /admin/demo/emit.
  - **릴로드:** "키워드 룰 리로드" → POST /admin/reload-keywords, "오디오 룰 리로드" → POST /admin/reload-audio-rules.

### 2-3. admin.js

- `API_BASE` 정의 (config 또는 `window.APP_CONFIG`).
- `fetch(API_BASE + "/admin/summary")` → JSON 파싱 후 DOM에 채우기.
- `fetch(API_BASE + "/admin/health")` → 동일.
- POST는 `fetch(url, { method: "POST" })` (body 필요 시 JSON 등).
- 버튼 클릭 시 해당 API 호출 후 상태 메시지(성공/실패) 표시.

### 2-4. (시간 있으면) GET /admin/alerts

- 알림 목록 테이블/리스트 추가.
- 첫 로딩: `GET /admin/alerts?limit=50`.
- 더 불러오기: `until_ts_ms = next_until_ts_ms - 1` (api_contract의 무한 스크롤 규칙).
- `isLoading` 플래그로 동시 요청 방지.

### 2-5. (시간 있으면) 피드백 집계

- GET /admin/feedback-summary, GET /admin/feedback-suspects → 테이블로 표시.

---

## 3. (나중에) 커스텀 구문 오디오

- **POST /custom-phrase-audio**, **GET /custom-phrase-audio**  
  폼: `name`, `event_type`(alert|danger), `threshold_pct`, `file`.  
  새 페이지 또는 new_sound에 탭 추가 후 위 API 연동.

---

## 체크리스트

| 항목 | 완료 |
|------|------|
| POST /custom-sounds (new_sound 제출) | ✅ |
| GET /custom-sounds (목록 탭) | ✅ |
| GET /logs (라이브 첫 로딩 + 더 불러오기) | [ ] |
| 관리자: summary, health, demo/emit, reload | [ ] |
| 관리자: alerts 목록 (선택) | [ ] |
| 관리자: feedback-summary, feedback-suspects (선택) | [ ] |
| 커스텀 구문 오디오 (나중에) | [ ] |

이 가이드만 따라가면 오늘 할 수 있는 범위까지 순서대로 진행할 수 있습니다.
