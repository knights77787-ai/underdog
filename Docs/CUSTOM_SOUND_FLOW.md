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
                              유사도/음압/말소리 가드 통과 시 alert 브로드캐스트
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
_rank_custom_sounds_by_similarity(session_id, emb_live_candidates):
  - DB에서 같은 session_id(로그인 사용자는 user_id 포함) 커스텀 소리 조회
  - 각 소리의 embedding과 live 후보(여러 1초 윈도우)의 최대 코사인 유사도 계산
  - _resolve_custom_pick으로 top1/top2 애매 구간 보정 후 후보 선택
    ↓
매칭 시:
  - DB에 alert 이벤트 저장
  - WebSocket으로 해당 session에 alert 브로드캐스트
  - 메인 화면: 실시간 자막 + 경고 배너 + 토스트 표시
```

### 2-4. YAMNet 클래스(521종) 등록 방식

- YAMNet(TF Hub)은 **521개** 환경음 클래스를 내며, 표시 이름은 `Backend/App/resources/yamnet_class_map.csv` 와 동일해야 한다.
- 전체 521 라벨 카탈로그는 `Shared/constants/yamnet_class_catalog.json` 이고, 운영 분류는 `Shared/constants/event_types.json` 의 선별 라벨 목록을 사용한다.
- **`warning_labels` → `caution_labels` → `daily_labels`** 순으로 매칭하므로, 사이렌·기차·차량 경적·개(`Dog`/`Animal`) 등은 기존처럼 **위험/주의가 우선**이다.
- 전체 목록(인덱스·mid·이름)은 `Shared/constants/yamnet_class_catalog.json` 에 JSON으로도 있다(검색·문서용).
- **주의**: 클래스에 `Speech`, `Conversation` 등 **말소리**도 포함된다. 주변 대화가 크면 비언어 알림이 잦아질 수 있어, 필요하면 `min_score` 를 올리거나 `daily_labels` 에서 일부만 남기도록 다시 줄인다.
- **`yamnet_skip_alert_labels`**: 말소리·웃음·울음·숨·기침·군중 말잡음(`Chatter`/`Crowd`/`Hubbub…`)·`Silence` 등 **비언어 알림에서 제외**할 YAMNet `display_name` 목록. `classify_audio` 단계에서 매칭 전에 건너뛴다(저장·WS·캐시 없음). 라벨은 CSV와 완전 일치.
- **개 짖음 보조 (`audio_cls_worker`)**: `Bark`/`Dog`/`Bow-wow`/`Yip`/`Whimper (dog)`/`Growling` 중 점수 최고가 `max(0.20, min_score×0.55)` 이상이면 (1) 1위가 매칭 실패이거나 (2) 1위가 생활알림인데 `Music`·`TV`·실내·잡음 등 **헷갈리는 daily**이거나 (3) 1위 점수와 거의 비슷하면 **개 짖음 라벨로 덮어씀**. 위험(danger) 1위는 유지.
- **Siren**: YAMNet 클래스 `Siren` 은 `warning_labels`에 넣어 경고 티어로 통일 가능(기존엔 daily만 있어 로그가 달랐음).
- 룰 수정 후: 서버 재시작 또는 `POST /admin/reload-audio-rules` (관리 토큰).

### 2-5. 유사도 임계값 (커스텀 소리)

- 변수명은 `CUSTOM_SOUND_*` 계열을 사용한다.
- 주요값: `CUSTOM_SOUND_THRESHOLD`, `CUSTOM_SOUND_THRESHOLD_LOUD`, `CUSTOM_SOUND_MIN_RMS`,
  `CUSTOM_SOUND_TOP2_MIN_GAP`, `CUSTOM_SOUND_SPEECH_BLOCK_SCORE`, `CUSTOM_SOUND_COOLDOWN_SEC`.
- 개별 등록음은 `match_threshold`(DB 컬럼)로 전역값보다 우선 적용할 수 있다.

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
| `Shared/constants/yamnet_class_catalog.json` | YAMNet 521 클래스 인덱스·mid·`display_name` 참고용 |
| `Shared/constants/event_types.json` | `audio_rules.daily_labels` 에 521 라벨 + `warning`/`caution` 우선 |

---

## 6. ENABLE_ML_WORKERS

커스텀 소리 매칭은 **YAMNet 워커**가 켜져 있을 때만 동작합니다.

- `.env` 에 `ENABLE_ML_WORKERS=1` 설정
- 서버 재시작 후 `AUDIOCLS_QUEUE` → `AudioClsWorker` 가 처리

비활성화 시: REST API는 동작하지만, 실시간 소리 감지·커스텀 매칭은 실행되지 않습니다.
