# REST API 응답 규격

## GET /logs

최근 로그 조회. 쿼리: `type`(all|caption|alert), `limit`, `session_id`, `since_ts_ms`, `until_ts_ms`.

### 응답 예시

```json
{
  "ok": true,
  "type": "all",
  "session_id": null,
  "limit": 100,
  "count": 2,
  "data": [
    {
      "type": "alert",
      "event_type": "danger",
      "keyword": "비상",
      "session_id": "sess-abc",
      "text": "비상 상황입니다",
      "ts_ms": 1730123456790
    },
    {
      "type": "caption",
      "session_id": "sess-abc",
      "text": "안녕하세요",
      "ts_ms": 1730123456789
    }
  ]
}
```

---

## GET /admin/summary

관리자 요약. 쿼리: `session_id`, `since_ts_ms`, `until_ts_ms`, `recent_window_sec`(기본 300).

### 응답 예시

```json
{
  "ok": true,
  "summary": {
    "session_id": null,
    "total_captions": 10,
    "total_alerts": 2,
    "alerts_recent": {
      "window_sec": 300,
      "count": 1,
      "since_ts_ms": 1730123300000
    },
    "unique_sessions": 1,
    "session_ids": ["sess-abc"],
    "last_event_ts_ms": 1730123456790,
    "last_event": {
      "type": "alert",
      "event_type": "danger",
      "keyword": "비상",
      "session_id": "sess-abc",
      "text": "비상 상황입니다",
      "ts_ms": 1730123456790
    }
  }
}
```

---

## POST /feedback

이벤트 피드백 저장. Body: `event_id`, `vote`(up|down), `comment`(선택), `client_session_uuid`(선택).

### 요청 예시

```json
{
  "event_id": 1,
  "vote": "up",
  "comment": "정확해요",
  "client_session_uuid": "sess-abc"
}
```

### 응답 예시

```json
{
  "ok": true,
  "feedback_id": 1,
  "event_id": 1,
  "vote": "up"
}
```
