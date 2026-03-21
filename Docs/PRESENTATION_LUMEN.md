# Lumen 발표용 문서 (Underdog)

> 팀명 **Underdog** · 서비스명 **Lumen** · 청각장애인을 위한 STT·환경음 기반 실시간 자막·알림 서비스  
> 발표 총 **40분** (기술 시연·질의응답 제외 시 기술 발표 약 **20분**)  
> 청중: 선생님, 업체 멘토 · 팀원 **2명** (기획·설계·구현 전반)

---

## 팀 역할 분담

### 팀원 1 (백엔드 집중: 실시간 파이프라인 + 서버 배포)
- WebSocket 실시간 파이프라인 구현: `audio_chunk` 수신 → VAD 분리 → Whisper(STT) 처리 → `caption` 생성/브로드캐스트
- 비언어/확장 처리 구현: YAMNet 기반 `alert` 생성 + 커스텀 소리(개 짖는 소리) 매칭 이벤트 처리
- 서버 배포/운영 준비 담당
- 모바일 배포 준비(기술): APK/AAB 생성 및 Google Play 내부 테스트 트랙 등록 진행 중(개발자 계정 승인 대기)

### 팀원 2 (프론트/관리자/연동 전담)
- 커스텀 소리 등록 화면 및 연동 구현(`new-sound`)
- 프론트 핵심 구현: 마이크 입력 처리, `audio_chunk` 전송, 실시간 자막/최근 감지 로그/UI 연결
- 위험도 로직 통합: 언어·비언어 결과를 `danger` 우선으로 UI에 강조(표시/중복 제어 포함)
- 이벤트 저장/기록 연동: UI에서 최근 감지 로그 및 기록 저장 흐름 연동(SQLite 기반)
- 관리자(Admin) 페이지 및 관리자 API 연동 구현
- OAuth 로그인/연동 흐름 구현

### 공통
- “언어(STT) + 비언어(사이렌/커스텀 소리)” 혼합 입력 데모 시나리오가 안정적으로 동작하도록 연동/테스트/튜닝

## 1. 발표 목표

1. **언어(STT)**: 마이크 음성 → Whisper STT → 실시간 **자막(caption)** 출력  
2. **비언어(YAMNet)**: 사이렌 등 환경음 → YAMNet 분류 → **자막·알림(alert)** 출력  
3. **커스텀 소리**: 개 짖는 소리 등 → **커스텀 소리 등록**(`danger`) → 임베딩 유사도 매칭 → 자막·알림  
4. **혼합 입력**: 마이크에 **언어 + 비언어가 동시에** 들어올 때, **위험도(danger)가 높은 쪽**이 UI에서 우선 강조되는 흐름 시연

---

## 2. 슬라이드 구성 (추천 14장)

| # | 제목 |
|---|------|
| 1 | 프로젝트 한 줄 소개 (Underdog / Lumen) |
| 2 | 접근성 문제 정의 |
| 3 | 해결 전략 (실시간 오디오 → STT / 환경음 → 자막·알림) |
| 4 | 전체 아키텍처 (Frontend ↔ WebSocket ↔ Backend Workers ↔ SQLite) |
| 5 | UI 구성 (실시간 자막, 최근 감지 로그, 마이크, 피드백) |
| 6 | WebSocket 프로토콜 (`join`, `audio_chunk`, `caption` / `alert`) |
| 7 | 언어 파이프라인: VAD(Silero) → 말 구간 → Whisper API → 자막 |
| 8 | 비언어 파이프라인: YAMNet(TFHub) → 룰 매핑 → `alert` |
| 9 | 커스텀 소리: 등록 임베딩 vs 실시간 임베딩 유사도 → 이벤트 |
| 10 | 위험도 기준: 키워드·오디오 룰 우선순위 (danger > caution > daily) |
| 11 | 혼합 입력(언어+비언어) 설계 |
| 12 | 안정성·성능 (큐/워커, `ENABLE_ML_WORKERS` 등) |
| 13 | 기술 시연 플로우 |
| 14 | 기대효과·결론·Q&A 안내 |

---

## 3. 기술 발표 대본 요약 (슬라이드별 톤)

### 오프닝·문제

- 청각 정보가 필요한 상황에서 **지연 없이** “무슨 말이 들렸는지”와 **위험 신호**를 동시에 전달하는 것이 목표다.  
- 단순 STT뿐 아니라 **환경음·커스텀 소리**를 같은 흐름으로 처리해 의미 있는 정보를 한 화면에 모은다.

### 아키텍처

- 프론트에서 마이크 오디오를 **WebSocket `audio_chunk`**(16kHz, PCM S16LE, base64)로 전송한다.  
- 백엔드는 **VAD로 말 구간**을 나누고 **Whisper API**로 STT한다.  
- 비언어는 **YAMNet**과 **커스텀 소리 임베딩 매칭**으로 이벤트를 만든다.  
- 결과는 같은 **`session_id`**에 **브로드캐스트**(`caption` / `alert`).  
- 이벤트는 **SQLite**에 저장할 수 있다.

### UI·프로토콜

- `index.html`: 왼쪽 **실시간 자막**, 오른쪽 **최근 감지 로그**, 마이크 버튼.  
- 흐름: `hello` → `join` → `join_ack` → `audio_chunk` → 수신 `caption` / `alert`.

### 언어(STT)

- **Silero VAD**로 speech start/end, 말 구간만 STT 큐에 넣음.  
- 짧은 구간·침묵 스킵, 긴 발화는 구간 컷으로 지연 완화.  
- **OpenAI Whisper API** (`whisper-1`, `language=ko`, `temperature=0.2` 등).  
- 활성 조건: `ENABLE_ML_WORKERS=1` 및 `OPENAI_API_KEY` 설정 시 STT 로드.

### 비언어(YAMNet)

- **TensorFlow Hub YAMNet**으로 1초 윈도우 등 분류.  
- `shared/constants/event_types.json`의 **`audio_rules`**로 danger / caution / daily 매핑.  
- 현재 예시: **사이렌**류는 `warning_labels` → **danger** 가능성 높음; **자동차 클락션**은 `caution_labels`의 `Vehicle horn, car horn, honking` → **caution** 쪽.

### 커스텀 소리 (개 짖는 소리)

- YAMNet 라벨에 직접 없을 수 있으므로 **`/new-sound`에서 커스텀 등록**, **`event_type=danger`** 권장.  
- 실시간 임베딩과 DB 임베딩 **코사인 유사도**로 매칭 후 `alert` → 프론트에서 자막·로그 반영.

### 위험도·혼합

- 텍스트 키워드: `keyword_detector` — **danger → caution → alert** 순 판정.  
- 오디오: `audio_rules`로 위험도 매핑.  
- **혼합 데모**: 사이렌(또는 커스텀 개 짖는 소리) 재생 중 **“불”** 등 danger 키워드를 말해, **danger가 UI에서 우선 강조**되는 것을 보여준다.

### 안정성

- **STT / YAMNet** 각각 큐·워커 구조, 과부하 시 드롭·쿨다운.  
- `ENABLE_ML_WORKERS` 미설정 시 무거운 워커 스킵(가벼운 기동).  
- 이벤트 정리: APScheduler 등(30일 초과 삭제 등).

---

## 4. 기술 시연 시나리오 (8~12분 권장)

1. **언어(STT)**  
   - 마이크로 **“불”** 포함 문장 (예: “불이야”, “불 조심해”)  
   - 실시간 자막 + 위험 강조 확인  

2. **비언어 — 사이렌**  
   - 마이크로 사이렌 소리 입력  
   - `alert`(source=`audio`) 및 자막/로그 반영  

3. **커스텀 — 개 짖는 소리**  
   - `new-sound`에서 개 짖는 소리 **`danger`로 등록**  
   - 동일 소리 재생 → 커스텀 매칭 알림·자막  

4. **혼합**  
   - 사이렌 또는 개 짖는 소리가 나는 동안 **“불”**을 말함  
   - 언어·비언어가 겹쳐도 **danger 중심**으로 화면이 강조되는지 설명  

**옵션**: 클락션은 `caution`에 가깝게 매핑되므로, “danger vs caution 차이”를 한 컷 넣을 수 있음.

---

## 5. 언어 데모 키워드: `불` 권장

- 백엔드 `event_types.json`의 danger 키워드에는 **`불`**, **`대피`** 모두 포함됨.  
- 프론트 `live.js`의 **`isDanger()`**는 자막 줄의 시각적 위험 강조에 **`불`은 포함**, **`대피`는 기본 목록에 없음**.  
- 발표에서 **자막 빨간 강조**까지 확실히 보이게 하려면 데모 문장에 **“불”**을 쓰는 것이 유리함.  
- “대피”도 강조하고 싶다면 `isDanger()`에 `"대피"` 추가하는 코드 수정을 검토.

---

## 6. 기술 스택 (코드 기준 요약)

| 구분 | 내용 |
|------|------|
| 백엔드 | FastAPI, Uvicorn, WebSocket, SQLAlchemy, SQLite (`underdog.db`) |
| STT | OpenAI Whisper API (`whisper-1`, 한국어) |
| VAD | Silero VAD |
| 환경음 | TensorFlow / TensorFlow Hub — YAMNet |
| 프론트 | HTML/CSS/JS, Bootstrap 5, Web Audio API → `audio_chunk` |
| 기타 | httpx, APScheduler, (선택) Firebase Admin 등 |

---

## 7. 질의응답 예상

1. **언어+비언어 동시에 들어오면?**  
   VAD·STT 경로와 YAMNet·커스텀 경로가 병렬로 동작하고, danger 이벤트가 UI에서 우선 강조되도록 설계.

2. **왜 VAD?**  
   말 구간만 STT해 호출 수·지연을 줄임.

3. **STT를 API로?**  
   서버 메모리·운영 부담을 줄이고 워커·큐로 처리 안정화.

4. **오탐·중복 알림?**  
   `cooldown_sec`, `alert_enabled`, `caption_all` 등 설정으로 조절.

5. **세션 ID가 왜 필요?**  
   같은 `session_id` 참가자에게만 브로드캐스트.

6. **개 짖는 소리는 YAMNet만으로?**  
   라벨 룰에 없을 수 있어 **커스텀 소리(danger)**로 데모·운영에 맞게 등록.

7. **무거운 서버 환경?**  
   `ENABLE_ML_WORKERS` 등으로 워커 비활성화 가능.

8. **피드백·저장?**  
   SQLite 저장, UI에서 `POST /feedback` 등으로 개선 데이터 수집.

---

## 8. 참고 파일 (레포 내)

- `Frontend/templates/index.html` — Lumen 메인 UI  
- `Frontend/static/js/live.js` — 마이크, WS, 자막, 알림, `isDanger()`  
- `Shared/ws_protocol.md` — WebSocket 메시지 규격  
- `shared/constants/event_types.json` — 키워드·`audio_rules`(사이렌/클락션 등)  
- `Backend/App/WS/handlers.py` — VAD, STT 큐, `audio_chunk` 처리  
- `Backend/App/WS/stt_worker.py` — Whisper 호출  
- `Backend/App/Services/stt_whisper_api.py` — Whisper API 클라이언트  
- `Backend/App/WS/audio_cls_worker.py` — YAMNet·커스텀 소리  
- `Frontend/INTEGRATION.md` — 프론트–백 연동 요약  

---

*문서 버전: 발표 준비용 초안 정리본*
