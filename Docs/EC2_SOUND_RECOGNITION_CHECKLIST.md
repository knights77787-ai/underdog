# 소리 인식이 안 될 때 점검 목록 (EC2 / 도메인)

실시간 자막·소리 감지가 **로컬(127.0.0.1)에서는 되는데 도메인(https://lumen.ai.kr)에서만 안 될 때** 아래를 순서대로 확인하세요.

---

## 1. WebSocket 연결 (가장 흔한 원인)

**증상:** 브라우저 콘솔에 `WebSocket connection to 'wss://lumen.ai.kr/ws' failed` 반복.

**이유:** nginx(또는 리버스 프록시)가 **/ws** 를 백엔드로 **업그레이드 전달**하지 않으면 wss 연결이 실패합니다. 그러면 마이크에서 보낸 오디오가 서버로 가지 않고, 자막/알림도 내려오지 않습니다.

**확인:**
- F12 → **Network** 탭 → **WS** 필터 → `/ws` 요청이 **101 Switching Protocols** 인지 확인.
- 101이 아니거나 실패하면 → **`Docs/EC2_WEBSOCKET_SETUP.md`** 와 **`Docs/nginx-lumen-ec2.conf.example`** 대로 nginx에 `location /ws { ... proxy_http_version 1.1; proxy_set_header Upgrade $http_upgrade; proxy_set_header Connection "upgrade"; ... }` 를 넣고 `sudo nginx -t` → `sudo systemctl reload nginx` 해주세요.
- **HTTPS(443)** 로 접속 중이라면, **listen 443 ssl** 인 server 블록 안에 위 `/ws` 설정이 있어야 합니다. (80만 있으면 wss는 동작하지 않습니다.)

---

## 2. 서버 ML 워커 비활성화

**증상:** WebSocket은 101로 연결되는데, 말해도 자막이 안 나오고 소리 감지도 안 됨.

**이유:** EC2에서 **ENABLE_ML_WORKERS** 가 설정되지 않으면 앱이 **가벼운 기동(light start)** 으로만 뜨고, STT(음성→자막)·YAMNet(소리 분류) 워커를 아예 띄우지 않습니다.

**확인:**
- EC2 서버에서 앱을 띄울 때 터미널 로그에  
  `ENABLE_ML_WORKERS not set; skipping yamnet/stt workers` 가 **안** 나와야 합니다.
- 나온다면 → **.env** 에 `ENABLE_ML_WORKERS=1` 이 들어가 있는지 확인하고, **.env가 프로젝트 루트 또는 Backend/** 에 있고 앱이 그걸 읽는지 확인한 뒤, 앱을 재시작하세요.

---

## 3. STT(음성→자막)용 OpenAI API 키

**증상:** WebSocket 연결됐고 ML 워커도 켜져 있는데, **말해도 자막만 안 나옴** (환경음 알림은 될 수 있음).

**이유:** 이 프로젝트는 STT에 **OpenAI Whisper API** 를 쓰도록 되어 있고, **OPENAI_API_KEY** 가 없으면 STT를 비활성화합니다.

**확인:**
- 앱 기동 로그에 `STT: disabled — OPENAI_API_KEY required but not set` 가 **안** 나와야 합니다.
- 나온다면 → **.env** 에 `OPENAI_API_KEY=sk-...` 를 넣고 앱을 재시작하세요. (EC2에 .env를 둘 때 보안에 주의.)

---

## 4. 마이크 권한 / HTTPS

**증상:** "마이크 사용 승인이 필요합니다" 만 나오거나, 마이크 버튼을 눌러도 소리 인식이 시작되지 않음.

**이유:** 브라우저는 **보안 출처(HTTPS 또는 localhost)** 에서만 `getUserMedia`(마이크)를 허용합니다. http://lumen.ai.kr 처럼 HTTP로 접속하면 마이크가 차단될 수 있습니다.

**확인:**
- 주소창이 **https://lumen.ai.kr** 인지 확인.
- 마이크 버튼 클릭 시 브라우저에서 **마이크 허용** 을 선택했는지 확인.
- F12 → Console 에 마이크/권한 관련 에러가 없는지 확인.

---

## 5. 한 줄 요약

| 확인 항목 | 할 일 |
|-----------|--------|
| WebSocket | F12 → Network → WS 에서 `/ws` 가 **101** 인지 확인. 아니면 nginx에 `/ws` 업그레이드 설정 추가 후 reload. |
| ML 워커 | EC2 .env에 `ENABLE_ML_WORKERS=1`, 앱 재시작 후 로그에 "skipping yamnet/stt" 가 안 나오는지 확인. |
| STT(자막) | .env에 `OPENAI_API_KEY` 설정, 앱 재시작 후 "OPENAI_API_KEY required but not set" 가 안 나오는지 확인. |
| 마이크 | https 로 접속했는지, 마이크 허용했는지 확인. |

위를 다 맞춰도 안 되면, EC2 앱 터미널 로그(기동 시 + 마이크 켠 뒤 요청/에러)와 브라우저 Network(WS 탭) 캡처를 보내주면 원인 좁히기 쉽습니다.
