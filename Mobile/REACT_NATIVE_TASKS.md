# React Native 모바일 앱 작업 목록

> Underdog 라이브 자막·알림 앱 – React Native (Expo)  
> 참고: `Shared/api_contract.md`, `Shared/ws_protocol.md`

---

## Phase 0: 환경 설정 ✅

| # | 작업 | 내용 |
|---|------|------|
| 0-1 | Expo 프로젝트 생성 | `Mobile/underdog-mobile` (TypeScript, blank-typescript) |
| 0-2 | 의존성 설치 | `expo-av`, `@react-navigation/native`, `react-native-screens`, `react-native-safe-area-context` |
| 0-3 | API/WS 설정 | `src/config.ts` – `API_BASE` / `WS_URL` (기본: `https://api.lumen.ai.kr`, `wss://api.lumen.ai.kr/ws`) |
| 0-4 | 네트워크 테스트 | `underdog-mobile/README.md` 참고 – REST는 `/health`, WS는 Phase 3에서 연결 시 확인 |

---

## Phase 1: 기본 구조 ✅

| # | 작업 | 내용 |
|---|------|------|
| 1-1 | 네비게이션 구조 | Stack: Login → Live. Live는 Bottom Tab(라이브, 설정, 커스텀 소리) |
| 1-2 | 세션 저장 | `src/storage/session.ts` + `SessionContext`: AsyncStorage에 `session_id` 저장, 앱 재시작 시 복원 |
| 1-3 | 공통 컴포넌트 | `src/components/`: Button(primary/secondary/outline), Card, Toast + ToastContext |

---

## Phase 2: 로그인

| # | 작업 | 내용 |
|---|------|------|
| 2-1 | 게스트 로그인 | POST /auth/guest → `session_id` 저장 → Live 화면으로 이동 |
| 2-2 | 구글 로그인 | `expo-auth-session` 또는 `@react-native-google-signin` → OAuth → 콜백에서 session_id 받기 |
| 2-3 | 카카오 로그인 | `@react-native-kakao-login` 또는 웹뷰 OAuth → 콜백 처리 |
| 2-4 | 로그인 화면 UI | 게스트/구글/카카오 버튼, 로딩/에러 상태 표시 |

**참고:** OAuth 콜백은 백엔드가 `underdog://live?session_id=xxx` 같은 딥링크로 리다이렉트하도록 설정 필요할 수 있음.

---

## Phase 3: 라이브 화면 (핵심) ✅

| # | 작업 | 내용 |
|---|------|------|
| 3-1 | WebSocket 연결 | `src/hooks/useLiveWs.ts` – `WS_URL` 연결, `join` 전송 (`session_id`) |
| 3-2 | caption 수신 | `caption` 수신 → 자막 영역 + 로그 목록에 추가 |
| 3-3 | alert 수신 | `alert` 수신 → 로그 목록 + Hero, `event_id` 보관 |
| 3-4 | Hero 영역 | 최근 알림 카드 (위험 시 강조) |
| 3-5 | Connect/Disconnect | 연결하기 / 연결 끊기 버튼 |
| 3-6 | 로그 목록 | caption/alert FlatList (최신 위, 500건 유지) |

---

## Phase 4: 마이크 (오디오 전송)

| # | 작업 | 내용 |
|---|------|------|
| 4-1 | 마이크 권한 | `expo-av` `Audio.requestPermissionsAsync()` |
| 4-2 | 오디오 녹음 | 16kHz mono PCM int16 스트림 획득 (expo-av 또는 react-native-audio-api) |
| 4-3 | 청크 전송 | 0.5초(8000 samples) 단위로 base64 인코딩 후 `audio_chunk` WS 메시지 전송 |
| 4-4 | 마이크 UI | 권한 요청 모달, 전송 중/중지 버튼 |

**참고:** `ws_protocol.md` – `audio_chunk` 형식 (sr: 16000, format: pcm_s16le, data_b64)

---

## Phase 5: 피드백

| # | 작업 | 내용 |
|---|------|------|
| 5-1 | 맞아요/아니에요 버튼 | alert 수신 시 `lastAlertEventId` 저장 |
| 5-2 | POST /feedback | `event_id`, `vote`(up/down), `session_id` 전송 |
| 5-3 | 토스트 | 성공/실패 메시지, "대상 알림이 없습니다" 안내 |

---

## Phase 6: 설정

| # | 작업 | 내용 |
|---|------|------|
| 6-1 | GET /settings | 로드 시 `session_id`로 조회 |
| 6-2 | POST /settings | 폰트 크기, 알림 on/off, 쿨다운, 자동 스크롤 변경 시 저장 |
| 6-3 | 설정 화면 UI | 입력 필드, 스위치, 저장 버튼 |

---

## Phase 7: 타이핑 자막 (선택)

| # | 작업 | 내용 |
|---|------|------|
| 7-1 | 입력 필드 | 텍스트 입력 + 전송 버튼 |
| 7-2 | send_caption | WS로 `{"type":"send_caption","session_id":"...","text":"..."}` 전송 |

---

## Phase 8: 과거 로그 (선택)

| # | 작업 | 내용 |
|---|------|------|
| 8-1 | GET /logs | Connect 후 첫 로딩, `until_ts_ms`로 더 불러오기 |
| 8-2 | FlatList | 무한 스크롤 또는 "더 불러오기" 버튼 |

---

## Phase 9: 커스텀 소리 (선택)

| # | 작업 | 내용 |
|---|------|------|
| 9-1 | POST /custom-sounds | 녹음/파일 선택 → FormData 업로드 |
| 9-2 | GET /custom-sounds | 목록 조회, 카드/리스트 표시 |

---

## Phase 10: 마무리

| # | 작업 | 내용 |
|---|------|------|
| 10-1 | 에러 처리 | 네트워크 끊김, WS 재연결, 권한 거부 안내 |
| 10-2 | 로딩/빈 상태 | 스피너, "연결 중…", "로그가 없습니다" 등 |
| 10-3 | Android 빌드 | `eas build` 또는 `expo prebuild` + `./gradlew assembleRelease` |
| 10-4 | iOS (선택) | Mac + Xcode 필요, 동일 코드로 빌드 가능 |

---

## 우선순위 요약

| 순서 | Phase | 설명 |
|------|-------|------|
| 1 | 0, 1 | 환경 + 기본 구조 |
| 2 | 2 | 로그인 (게스트만 먼저 가능) |
| 3 | 3 | 라이브 WS + caption/alert |
| 4 | 4 | 마이크 (핵심 기능) |
| 5 | 5, 6 | 피드백, 설정 |
| 6 | 7~10 | 타이핑, 과거 로그, 커스텀 소리, 마무리 |

---

## 참고 문서

- `Shared/api_contract.md` – REST API 스펙
- `Shared/ws_protocol.md` – WebSocket 메시지 스펙
- `Frontend/static/js/live.js` – 웹 구현 참고용
