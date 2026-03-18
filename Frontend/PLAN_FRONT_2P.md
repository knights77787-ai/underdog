# 프론트엔드 완성 · 2명 분담 계획

> **목표:** 현재까지 진행된 프론트를 기준으로, 오늘 안에 프론트 완성을 목표로 2명이 나눠서 작업한다.

---

## 1. 현재 진행 상황 요약

| 구역 | 상태 | 비고 |
|------|------|------|
| **라이브 (index + live.js)** | WS join, caption/alert 수신, 로그 테이블, Hero, 마이크 UI | 피드백 버튼은 **UI만** (POST /feedback 미연동), session_id 고정 "S1" |
| **커스텀 소리 (new_sound)** | POST /custom-sounds 연동 완료, 녹음·업로드·.wav | "내가 등록한 소리" 탭은 **링크만** 있고 목록 페이지 없음 |
| **로그인** | login.html, ad_login.html | **빈 파일** |
| **관리자** | admin.html | **빈 파일** |
| **설정** | - | GET/POST /settings **미연동** |

---

## 2. 역할 분담 개요

| 담당 | 담당자 A | 담당자 B |
|------|----------|----------|
| **테마** | 진입·라이브·설정 완성 | 커스텀 소리 목록 + 관리자 페이지 |
| **주요 페이지** | 로그인, 라이브(진입·피드백·설정) | new_sound 보강, 내 소리 목록, admin |
| **API 연동** | /auth/guest, /auth/google·kakao, /feedback, /settings | /custom-sounds GET, /custom-phrase-audio(선택), /admin/* |

---

## 3. 담당자 A — 진입·라이브·설정

### 3.1 로그인/진입 (login.html + CSS/JS)

- [ ] **login.html** 구현
  - 게스트: "게스트로 시작" 버튼 → `POST /auth/guest` → 응답 `session_id` 저장(예: localStorage 또는 쿼리 유지) → `/live?session_id=xxx` 로 이동
  - 구글: `window.location = API_BASE + '/auth/google/login'` (또는 링크)
  - 카카오: `window.location = API_BASE + '/auth/kakao/login'`
- [ ] **콜백 처리**  
  - 구글/카카오 로그인 후 서버가 `/live?session_id=xxx&provider=google` 등으로 리다이렉트하므로, **live 쪽**에서 URL 쿼리 `session_id`가 있으면 그걸 사용하도록 연동 (A가 live.js도 수정)

### 3.2 라이브 페이지 (index.html + live.js)

- [ ] **session_id 소스 통일**
  - URL 쿼리 `session_id` 있으면 사용
  - 없으면 `POST /auth/guest` 호출해서 `session_id` 받은 뒤 같은 페이지를 `?session_id=xxx` 로 교체하거나, 그대로 사용 후 WS/API에 동일 값 사용
- [ ] **피드백 연동**
  - 서버에서 **alert** 수신 시 `event_id` 포함해 "최근 알림 1건" 저장 (예: `lastAlertEventId`, `lastAlertPayload`)
  - "맞아요" → `POST /feedback` body: `{ event_id, vote: "up", comment?: "" }`
  - "아니에요" → `POST /feedback` body: `{ event_id, vote: "down", comment?: "" }`
  - `client_session_uuid`는 세션 식별용으로 선택 전달 (session_id와 동일해도 됨)
  - 성공 시 토스트 "피드백 저장됨", 4xx/5xx 시 토스트 에러
  - 아직 alert를 한 번도 안 받은 상태에서 버튼 클릭 시 "대상 알림이 없습니다" 안내
- [ ] **(여유 시) 설정 패널**
  - 라이브 상단/측면에 "설정" 접기/펼치기
  - 로드 시 `GET /settings?session_id=xxx` → 폰트 크기, 알림 on/off, 쿨다운, 자동 스크롤 등 표시
  - 변경 시 `POST /settings?session_id=xxx` body에 변경 필드만 JSON으로 merge

**참고:** `Shared/ws_protocol.md` 에 따르면 alert 메시지에 `event_id` 포함됨. `Shared/api_contract.md` 의 POST /feedback 스펙 참고.

---

## 4. 담당자 B — 커스텀 소리·관리자

### 4.1 커스텀 소리 보강

- [ ] **내가 등록한 소리 목록**
  - "내가 등록한 소리" 탭 클릭 시 보여줄 페이지 (또는 같은 new_sound.html 내 섹션)
  - `GET /custom-sounds?session_id=xxx` 호출 → 테이블/카드로 목록 렌더링 (`custom_sound_id`, `name`, `event_type`)
  - session_id는 URL 쿼리 또는 로그인/게스트와 동일한 방식으로 공유 (A와 협의)
- [ ] **(선택) 커스텀 구문 음성**
  - `POST/GET /custom-phrase-audio` 연동 페이지 하나 (이름·event_type·threshold_pct·파일 업로드). 시간 없으면 생략 가능.

### 4.2 관리자 페이지 (admin.html + admin.js + admin.css)

- [ ] **진입**
  - 관리자 전용 로그인(ad_login.html)은 **빈 파일**이므로, 오늘은 URL로 직접 진입 (예: `/admin`) 가능하게만 해도 됨. 필요 시 나중에 인증 추가.
- [ ] **대시보드 요약**
  - `GET /admin/summary` → total_captions, total_alerts, alerts_recent, last_event 등 표시
- [ ] **알림 목록 (무한 스크롤)**
  - `GET /admin/alerts?limit=50` 첫 로딩
  - 스크롤 끝에서 `until_ts_ms = next_until_ts_ms - 1` 로 "더 불러오기" (api_contract.md 규칙 준수)
  - 로딩 잠금, has_more 종료 처리
- [ ] **운영/시연용**
  - `GET /admin/health` → DB/worker/큐 상태 표시
  - `GET /admin/metrics` → 큐 크기·카운터·세션 수 등
  - `POST /admin/demo/emit` → 버튼 하나로 데모 이벤트 발생
  - `POST /admin/reload-keywords`, `POST /admin/reload-audio-rules` → 버튼으로 룰 핫리로드
- [ ] **피드백 집계 (선택)**
  - `GET /admin/feedback-summary`, `GET /admin/feedback-suspects` → 간단 테이블/리스트로 표시

**참고:** `Shared/api_contract.md` 의 GET /admin/alerts, GET /admin/summary, 무한 스크롤 규칙·필드 설명 참고.

---

## 5. 공통·협의 사항

- **API 베이스 URL**  
  - `live.js`, `new_sound.js`, `wsClient.js` 등에서 `API_BASE = "http://127.0.0.1:8000"` 사용 중. 배포 시 한 곳에서 바꿀 수 있게 공통 설정 파일이나 `window.APP_CONFIG` 등으로 빼두면 좋음.
- **session_id 공유**  
  - 로그인/게스트에서 받은 `session_id`를 라이브·커스텀 소리·설정에서 동일하게 쓸 수 있도록 규칙 통일 (쿼리 유지 vs localStorage 등). A가 진입 플로우를 만들므로, B는 "session_id는 쿼리 또는 A가 정한 방식으로 전달받는다"고 가정하면 됨.
- **스타일**  
  - index는 Bootstrap 5, new_sound는 자체 CSS. admin은 Bootstrap 5 재사용 권장. login은 index와 톤 맞추면 됨.

---

## 6. 완료 체크리스트 (오늘 목표)

- [ ] **A** 로그인 페이지에서 게스트/구글/카카오 진입 후 session_id 로 라이브 진입
- [ ] **A** 라이브에서 alert 수신 시 event_id 저장, 맞아요/아니에요 → POST /feedback 연동
- [ ] **A** (선택) 라이브 설정 GET/POST 연동
- [ ] **B** GET /custom-sounds 로 "내가 등록한 소리" 목록 표시
- [ ] **B** admin 페이지에서 summary, alerts(무한 스크롤), health, metrics, demo emit, reload 룰
- [ ] **공통** E2E 한 번씩: 진입 → 라이브 → 알림 수신 → 피드백 저장 / 커스텀 소리 등록·목록 / 관리자 요약·알림 확인

---

## 7. 참고 문서

- `Shared/api_contract.md` — REST API 응답·요청 규격 (로그, 설정, 피드백, admin, auth, custom-sounds 등)
- `Shared/ws_protocol.md` — WebSocket 메시지 (join, caption, alert, event_id)
- `Frontend/INTEGRATION.md` — 연동 체크리스트
- `Frontend/PLAN_2DAY.md` — 기존 2일 계획 (피드백·설정 중심)

이 순서대로 진행하면 두 명이 동시에 작업해도 충돌을 최소화하면서 프론트 완성까지 가져갈 수 있다.
