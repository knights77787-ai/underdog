# 오늘 프론트엔드 작업 + 모바일 예정 작업

> 작성일: 2025-03-12  
> 기준: 실제 코드베이스 상태 (완료/미완료)

---

## 1. 현재 완료된 것

| 구역 | 상태 |
|------|------|
| Live 메인 (index + live.js) | WS, 마이크, 자막, 로그, Hero, 피드백, 설정 패널 연동 완료 |
| 로그인 (login.html) | 게스트/Google/카카오, 세션 발급 후 Live 진입 |
| 커스텀 소리 (new_sound) | 녹음·업로드, 등록, 목록 탭, 재생·삭제, POST/GET/DELETE 연동 |
| WebSocket (wsClient.js) | connect/disconnect/send/on |

---

## 2. 오늘 할 프론트 작업

### 2-1. Admin 페이지 (우선)

| 작업 | 상세 |
|------|------|
| **main.py 라우트 추가** | `GET /admin` → `admin.html` 서빙 |
| **admin.html 구현** | Bootstrap 5 기반 레이아웃, 섹션 영역 구성 |
| **admin.js 구현** | 아래 API 연동 |

**admin.js 연동 목록**

| API | 용도 |
|-----|------|
| `GET /admin/summary` | total_captions, total_alerts, alerts_recent, last_event 표시 |
| `GET /admin/health` | db_ok, tasks, queues 상태 표시 |
| `POST /admin/demo/emit` | "데모 알림 1건" 버튼 |
| `POST /admin/reload-keywords` | "키워드 룰 리로드" 버튼 |
| `POST /admin/reload-audio-rules` | "오디오 룰 리로드" 버튼 |
| `GET /admin/alerts?limit=50` | 알림 목록 (무한 스크롤: until_ts_ms, next_until_ts_ms) |
| `GET /admin/feedback-summary` | (선택) 피드백 집계 |
| `GET /admin/feedback-suspects` | (선택) 오탐 의심 키워드 |

**참고:** `/admin/*` API는 `X-Admin-Token` 헤더 필요. `.env`에 `DEV=1`이면 토큰 생략 가능.

---

### 2-2. 네비게이션 보강

| 작업 | 상세 |
|------|------|
| **index.html** | 상단에 "커스텀 소리" 링크 추가 → `/new-sound?session_id=xxx` |
| **new_sound.html** | Lumen 브랜드 `href="#"` → `href="/"` 또는 `href="/?session_id=xxx"` |
| **session_id 유지** | 링크 이동 시 쿼리로 session_id 전달 |

---

### 2-3. config.js (선택)

| 작업 | 상세 |
|------|------|
| **config.js 작성** | `window.APP_CONFIG = { API_BASE, WS_URL, LIVE_PATH }` |
| **live.js, new_sound.js** | `API_BASE = window.APP_CONFIG?.API_BASE \|\| "http://127.0.0.1:8000"` 유지 (config 로드 시 덮어씀) |

---

## 3. 앞으로 할 모바일 작업

### 3-1. 현재 모바일 상태

- `viewport` 메타 태그 있음 (index, login, new_sound)
- Bootstrap 그리드 사용 (`col-12 col-lg-8` 등) → 기본 반응형
- new_sound.css에 `@media (max-width: 768px)` 1곳 (sound-row 레이아웃)

### 3-2. 모바일 보강 필요 항목

| 페이지 | 작업 | 상세 |
|--------|------|------|
| **index (Live)** | Topbar 오버플로우 | Connect/Disconnect/설정/배지 등이 좁은 화면에서 넘침 → 햄버거 메뉴 또는 스크롤/랩 |
| **index** | 설정 패널 | 모바일에서 col-auto들이 세로로 쌓이도록 `flex-wrap` 또는 `flex-column` |
| **index** | 테이블 스크롤 | 로그 테이블 `overflow-x: auto` 확인, 가로 스크롤 가능하게 |
| **index** | 터치 타겟 | 버튼 최소 44x44px (접근성) |
| **index** | 자막 영역 | caption-box 높이를 `min-height` + `vh`로 모바일에서 더 활용 |
| **new_sound** | 녹음/업로드 영역 | 작은 화면에서 버튼·입력 폼 여백·터치 영역 점검 |
| **new_sound** | 소리 목록 | 카드/리스트 터치 영역, 삭제 버튼 간격 |
| **login** | 폼 레이아웃 | 이미 `col-12 col-md-8 col-lg-5` 사용 중 → 추가 확인 |
| **admin** | (미구현) | 처음부터 모바일 고려해서 레이아웃 설계 |

### 3-3. 공통 모바일 작업

| 작업 | 상세 |
|------|------|
| **Safe area** | `env(safe-area-inset-*)` 적용 (노치·홈 인디케이터 대응) |
| **폰트 크기** | 모바일에서 `font-size` 최소 16px (줌 방지) |
| **스와이프 제스처** | (선택) 탭 전환 등 제스처 지원 |
| **PWA** | (선택) manifest, service worker로 앱처럼 설치 |

---

## 4. 오늘 체크리스트

- [ ] `main.py`에 `GET /admin` → `admin.html` 라우트 추가
- [ ] `admin.html` 기본 레이아웃 작성
- [ ] `admin.js` summary, health, demo emit, reload 연동
- [ ] (여유 시) admin alerts 무한 스크롤
- [ ] index ↔ new_sound 네비게이션 링크 추가

---

## 5. 참고 문서

- `Shared/api_contract.md` — REST API 규격 (admin, alerts, feedback 등)
- `Shared/ws_protocol.md` — WebSocket 메시지
- `Frontend/INTEGRATION.md` — 연동 체크리스트
