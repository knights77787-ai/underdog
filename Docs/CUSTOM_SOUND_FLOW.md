# 내가 등록한 소리 → 실시간 감지 연동 흐름

등록한 커스텀 소리가 메인 화면 실시간 소리 감지에서 어떻게 인식되는지 설명합니다.

---

## 1. 전체 흐름 요약

```
[소리 등록]                    [실시간 감지]
new_sound 페이지    ────────►  live(메인) 페이지
POST /custom-sounds            마이크 → WebSocket → 서버
  ↓                                ↓
DB에 embedding 저장            AUDIOCLS_QUEUE
  ↓                                ↓
client_session_uuid = 세션ID    세션별 custom sound와 유사도 비교
                                    ↓
                              유사도 ≥ 0.75 → 알림(alert) 브로드캐스트
```

**핵심**: **같은 `session_id`** 로 등록하고, 같은 `session_id` 로 라이브에서 마이크를 켜야 연동됩니다.

---

## 2. 단계별 설명

### 2-1. 소리 등록 (new_sound 페이지)

| 단계 | 내용 |
|------|------|
| 진입 | 라이브 → 사용자 드롭다운 → "소리등록" 클릭 → `/new-sound?session_id=xxx` |
| 녹음/업로드 | 오디오 파일 선택 후 이름·분류 입력 |
| 등록 | `POST /custom-sounds?session_id=xxx` (FormData: name, event_type, file) |
| 서버 처리 | 오디오를 16kHz mono float32로 변환 → YAMNet으로 **embedding 추출** → DB 저장 |

**저장되는 것**
- `client_session_uuid`: 등록 시 사용한 `session_id` (예: OAuth UUID)
- `embed_blob`, `embed_dim`: 1024차원 YAMNet embedding (정규화됨)
- `name`, `event_type`, `audio_path` 등

### 2-2. 실시간 감지 (live 페이지)

| 단계 | 내용 |
|------|------|
| 마이크 켜기 | "마이크 실행" 클릭 → WebSocket 연결 → `join` 전송 (`session_id`) |
| 오디오 전송 | 2초 청크를 `audio_chunk` 로 전송 (`session_id`, pcm_s16le 16kHz) |
| **커스텀 소리 경로** | VAD와 무관하게 항상 4초 윈도우(2초×2청크) 수집 → `AUDIOCLS_QUEUE` 적재 |
| VAD | 음성 구간은 STT로, 비음성은 별도 처리 (커스텀 소리는 둘 다 큐에 포함) |

### 2-3. 백엔드 매칭 (AudioClsWorker)

```
AUDIOCLS_QUEUE에서 4초 오디오 꺼냄
    ↓
YAMNet embedding_1s(audio) → emb_live (1024차원)
    ↓
_match_custom_sound(session_id, emb_live):
  - DB에서 client_session_uuid == session_id 인 커스텀 소리만 조회
  - 각 소리의 embedding과 emb_live의 코사인 유사도 계산 (dot product, 정규화됨)
  - 유사도 최댓값 ≥ 0.75 이면 해당 소리로 매칭
    ↓
매칭 시:
  - DB에 alert 이벤트 저장
  - WebSocket으로 해당 session에 alert 브로드캐스트
  - 메인 화면: 실시간 자막 + 경고 배너 + 토스트 표시
```

### 2-4. 유사도 임계값

- `CUSTOM_THRESHOLD = 0.75` (audio_cls_worker.py)
- 0.75 이상이면 같은 소리로 판단
- 환경/녹음 품질에 따라 0.75~0.9 사이로 조정 가능

---

## 3. session_id 일치가 중요한 이유

| 상황 | session_id | 결과 |
|------|------------|------|
| OAuth 로그인 후 라이브 | URL에 `session_id=uuid` | 라이브·소리등록 모두 동일 uuid 사용 |
| 소리등록 드롭다운 클릭 | `/new-sound?session_id=uuid` 전달 | 등록 시 `client_session_uuid=uuid` 로 저장 |
| 라이브 마이크 켜기 | `join`, `audio_chunk` 에 `session_id=uuid` | 매칭 시 `client_session_uuid == uuid` 인 소리만 검색 |

**다르면**: 등록은 A 세션, 라이브는 B 세션 → 서로 다른 DB 레코드를 보므로 매칭되지 않습니다.

---

## 4. 사용자용 체크리스트

1. **로그인** (Google/카카오) 후 라이브 페이지 진입
2. **소리등록** 메뉴에서 같은 계정으로 소리 등록
3. **라이브로 돌아와서** 마이크 켜기
4. 등록한 소리와 **비슷한 소리**를 재생하면 → 실시간 자막/경고 표시

---

## 5. 관련 파일

| 파일 | 역할 |
|------|------|
| `Frontend/static/js/live.js` | 마이크 → `audio_chunk` 전송, `session_id` 포함 |
| `Frontend/static/js/new_sound.js` | `POST /custom-sounds`, `session_id` 쿼리로 전달 |
| `Backend/App/WS/handlers.py` | `audio_chunk` 수신 → VAD(음성→STT) / 커스텀소리(VAD 무관) → AUDIOCLS_QUEUE 적재 |
| `Backend/App/WS/audio_cls_worker.py` | embedding 계산, `_match_custom_sound`, alert 브로드캐스트 |
| `Backend/App/Api/routes/custom_sounds.py` | 등록 시 YAMNet embedding 계산 후 DB 저장 |

---

## 6. ENABLE_ML_WORKERS

커스텀 소리 매칭은 **YAMNet 워커**가 켜져 있을 때만 동작합니다.

- `.env` 에 `ENABLE_ML_WORKERS=1` 설정
- 서버 재시작 후 `AUDIOCLS_QUEUE` → `AudioClsWorker` 가 처리

비활성화 시: REST API는 동작하지만, 실시간 소리 감지·커스텀 매칭은 실행되지 않습니다.
