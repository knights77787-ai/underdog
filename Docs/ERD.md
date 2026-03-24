# Underdog DB ERD

SQLAlchemy 모델 기준: `Backend/App/db/models.py`  
SQLite: `Backend/data/underdog.db` (배포 환경에 따라 경로 상이할 수 있음)

## 관계 요약

- **User** — 선택적으로 여러 **Session**, **CustomSound**, **EventFeedback**, **DeviceToken**과 연결 (`user_id` nullable인 경우 많음: 게스트·세션 UUID 기반 흐름).
- **Session** — **User**에 속함(optional), **Settings**와 1:1, **Event** 1:N.
- **Event** — **Session**에 속함, **EventTranscript**·**EventFeedback** 1:N.
- **CustomPhraseAudio** / 일부 **CustomSound**·**DeviceToken**은 `client_session_uuid`로 세션과 **논리적**으로만 연결(FK 없음).

아래 다이어그램은 VS Code / GitHub에서 Mermaid로 렌더링됩니다.

```mermaid
erDiagram
    users {
        int user_id PK
        string email
        string name
        string oauth_provider
        string oauth_sub
        datetime created_at
    }

    sessions {
        int session_id PK
        int user_id FK
        bool is_guest
        bool recording_enabled
        string client_session_uuid
        datetime start_time
        datetime end_time
    }

    settings {
        int settings_id PK
        int session_id FK
        text data_json
    }

    events {
        int event_id PK
        int session_id FK
        string event_type
        float danger_score
        float alert_score
        text topk_labels
        int matched_custom_sound_id
        float custom_similarity
        int segment_start_ms
        int segment_end_ms
        float vad_confidence
        int latency_ms
        string keyword
        datetime created_at
    }

    event_transcripts {
        int transcript_id PK
        int event_id FK
        text text
        datetime created_at
    }

    event_feedback {
        int feedback_id PK
        int event_id FK
        int user_id FK
        string client_session_uuid
        string vote
        string comment
        datetime created_at
    }

    custom_sounds {
        int custom_sound_id PK
        int user_id FK
        string client_session_uuid
        string name
        string event_type
        string match_target
        string audio_path
        int embed_dim
        blob embed_blob
        datetime created_at
    }

    custom_phrase_audio {
        int custom_phrase_id PK
        string client_session_uuid
        string name
        string event_type
        int threshold_pct
        string audio_path
        int embed_dim
        blob embed_blob
        datetime created_at
    }

    device_tokens {
        int device_token_id PK
        int user_id FK
        string client_session_uuid
        string platform
        string token
        datetime created_at
        datetime updated_at
    }

    users ||--o{ sessions : "user_id"
    sessions ||--|| settings : "session_id"
    sessions ||--o{ events : "session_id"
    events ||--o{ event_transcripts : "event_id"
    events ||--o{ event_feedback : "event_id"
    users ||--o{ custom_sounds : "user_id"
    users ||--o{ event_feedback : "user_id"
    users ||--o{ device_tokens : "user_id"
```

## 제약·비관계 필드

| 항목 | 설명 |
|------|------|
| `uq_settings_session_id` | 세션당 설정 1건 |
| `uq_feedback_event_session` | 동일 `(event_id, client_session_uuid)` 피드백 중복 방지 |
| `uq_device_tokens_token` | 토큰 유일 |
| `events.matched_custom_sound_id` | 정수 참조만 있음 ORM FK 아님 |
| `custom_phrase_audio`, `custom_sounds`(일부), `device_tokens` | `client_session_uuid`로 세션과 앱 레벨 매칭 |
