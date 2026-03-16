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

## Phase 2: 로그인 ✅

| # | 작업 | 내용 |
|---|------|------|
| 2-1 | 게스트 로그인 | POST /auth/guest → `session_id` 저장 → Live 화면으로 이동 |
| 2-2 | 구글 로그인 | `expo-web-browser`로 `/auth/google/login?mobile=1` 오픈 → 백엔드가 `/auth/mobile-done` → `underdog://live?session_id=...` → 앱에서 Linking으로 수신 후 세션 저장 |
| 2-3 | 카카오 로그인 | 동일하게 `/auth/kakao/login?mobile=1` → mobile-done → 딥링크 |
| 2-4 | 로그인 화면 UI | 게스트 / Google / 카카오 버튼, 로딩·에러·토스트 |

**백엔드:** `Backend/App/Api/routes/auth.py` – `?mobile=1` 시 `state=mobile` 전달, 콜백 후 `/auth/mobile-done`(HTML에서 `underdog://live?...` 리다이렉트). 앱 `app.json`에 `scheme: "underdog"` 등록.

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

## Phase 4: 마이크 (오디오 전송) ✅

| # | 작업 | 내용 |
|---|------|------|
| 4-1 | 마이크 권한 | `expo-av` `Audio.requestPermissionsAsync()`, 거부 시 안내 |
| 4-2 | 오디오 스트림 | expo-av Recording으로 마이크 사용. 현재 전송은 **침묵 청크**(0.5초 PCM int16)로 파이프라인 검증. 실제 음성 PCM은 개발 빌드 + 네이티브 캡처 모듈로 확장 가능 |
| 4-3 | 청크 전송 | 0.5초(8000 samples) base64 → `useLiveWs.sendAudioChunk` → `audio_chunk` WS |
| 4-4 | 마이크 UI | 라이브 탭에 마이크 카드, 켜기/끄기 버튼, 권한 거부 시 문구 |

**참고:** `ws_protocol.md` – `audio_chunk` (sr: 16000, format: pcm_s16le, data_b64)

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
