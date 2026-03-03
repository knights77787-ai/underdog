# WebSocket 메시지 예시 (최종 4종)

## hello (서버 → 클라이언트)

연결 수락 직후 서버가 한 번 보냄.

```json
{"type": "hello"}
```

---

## join_ack (서버 → 클라이언트)

클라이언트가 `join` 보낸 뒤 서버가 응답.

```json
{"type": "join_ack", "session_id": "sess-abc"}
```

---

## caption (서버 → 클라이언트, 같은 세션 브로드캐스트)

자막/STT 결과. 같은 세션 참가자에게 브로드캐스트.

```json
{
  "type": "caption",
  "session_id": "sess-abc",
  "text": "안녕하세요",
  "ts_ms": 1730123456789
}
```

---

## alert (서버 → 클라이언트, 같은 세션 브로드캐스트)

키워드 등으로 감지된 알림. `event_type`은 `danger` 또는 `alert`.

```json
{
  "type": "alert",
  "event_type": "danger",
  "keyword": "비상",
  "session_id": "sess-abc",
  "text": "비상 상황입니다",
  "ts_ms": 1730123456790
}
```
