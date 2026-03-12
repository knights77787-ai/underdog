# 이미지 기준 남은 코딩 작업

> 이미지(2~6번)에 나온 작업과 현재 코드베이스 비교

---

## 2) WebSocket "자동 재연결 + 백오프 + 상태표시"

### 현재 상태
| 항목 | 웹 (live.js + wsClient) | RN (UnderdogMobile) |
|------|-------------------------|---------------------|
| 연결중/연결됨/끊김 UI | ⚠️ 연결됨/끊김만 (Disconnected/Connected) | ❌ WebSocket 미구현 |
| 끊기면 1s→2s→4s→8s... 재시도 | ❌ 없음 | ❌ |
| 최대 30s 백오프 | ❌ | ❌ |
| 앱 백그라운드 복귀 시 재연결 | N/A (웹) | ❌ |

### 남은 작업
- **웹:** wsClient.js에 자동 재연결 + exponential backoff (1s→2s→4s→8s, max 30s) + "연결중" 상태 추가
- **RN:** WebSocket 연결 화면 구현 시 위 로직 포함

---

## 3) 마이크 스트리밍 파이프라인 정리

### 현재 상태
| 항목 | 웹 (live.js) | RN |
|------|--------------|-----|
| chunk 전송 중복 방지 | ✅ buffer splice로 1회만 전송 | N/A (스트리밍 미구현) |
| stop 시 리스너 제거 | ✅ stopAudioSend에서 disconnect | N/A |
| 에러 시 clean-up | ⚠️ try/catch 있으나 onerror 리스너 정리 확인 필요 | N/A |

### 남은 작업
- **웹:** audioWorkletNode/audioProcessor 에러 핸들러에서 stopAudioSend() 호출 여부 확인
- **RN:** 마이크 스트리밍 구현 시 중복 방지·리스너 제거·에러 clean-up 설계

---

## 4) 이벤트/자막 로그 로컬 저장 + 서버 업로드 큐

### 현재 상태
| 항목 | 웹 | RN |
|------|-----|-----|
| 로컬 최근 200개 저장 | ❌ DOM에만 표시 (30건 유지) | ❌ |
| 시간/자막/분류/에러코드 | ❌ | ❌ |
| 네트워크 꺼져도 쌓았다가 업로드 | ❌ | ❌ |
| AsyncStorage (설정) | ❌ | ❌ |
| SQLite/realm (이벤트 로그) | N/A | ❌ |

### 남은 작업
- **웹:** localStorage 또는 IndexedDB로 최근 200건 저장, 오프라인 시 큐에 쌓았다가 복구 시 업로드
- **RN:** AsyncStorage(설정) + react-native-sqlite-storage 또는 realm(이벤트 로그 200건), 업로드 큐

---

## 5) 알림 UX 완성 (진동/플래시/큰 자막/위험 배너)

### 현재 상태
| 항목 | 웹 | RN |
|------|-----|-----|
| Danger 배너 | ✅ Hero 카드 | N/A |
| 진동 패턴 | ✅ vibrateByLevel(danger/alert) | ✅ haptics.js (impactHeavy/Light) |
| 플래시 | ❌ | ❌ |
| 큰 자막 | ✅ caption-box (설정으로 폰트 크기) | N/A |
| 오탐/정탐 피드백 버튼 | ✅ 맞아요/아니에요 | N/A |

### 남은 작업
- **웹:** (선택) 위험 시 화면 플래시 효과
- **RN:** WebSocket/alert 연동 시 Danger 배너 + vibrateByLevel 호출

---

## 6) 릴리즈 빌드

### 현재 상태
| 항목 | 상태 |
|------|------|
| android:usesCleartextTraffic | ⚠️ manifest에 `${usesCleartextTraffic}` (변수) - gradle에서 true 설정 필요 |
| 프로덕션 https/wss | 설계 필요 |
| Release에서 권한/마이크/WS 확인 | 수동 테스트 필요 |

### 남은 작업
- **RN android:** build.gradle defaultConfig에 `manifestPlaceholders = [usesCleartextTraffic: "true"]` (개발용). 프로덕션 빌드 시 false
- **Release 빌드:** `./gradlew assembleRelease` 후 실제 기기에서 마이크·WS 동작 확인

---

## 우선순위 요약

| 순위 | 작업 | 대상 | 난이도 |
|------|------|------|--------|
| 1 | WebSocket 자동 재연결 + 백오프 | 웹 wsClient | 중 |
| 2 | 연결중 상태 UI | 웹 | 하 |
| 3 | 이벤트 로그 로컬 저장 (200건) | 웹/RN | 중 |
| 4 | RN usesCleartextTraffic gradle 설정 | RN | 하 |
| 5 | 업로드 큐 (오프라인 대응) | 웹/RN | 상 |
| 6 | (선택) 화면 플래시 | 웹 | 하 |
