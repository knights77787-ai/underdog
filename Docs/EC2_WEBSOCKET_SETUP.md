# EC2에서 WebSocket(wss://) 연결하기

도메인(`https://lumen.ai.kr`)으로 접속 시 **실시간 자막·소리 감지**가 동작하려면 **WebSocket** (`wss://lumen.ai.kr/ws`) 연결이 성공해야 합니다.  
로컬(`127.0.0.1:8000`)에서는 되는데 도메인에서만 "WebSocket connection to 'wss://lumen.ai.kr/ws' failed" 가 나온다면, **리버스 프록시(nginx 등)에서 `/ws` 를 백엔드로 업그레이드 전달**하지 않았기 때문입니다.

---

## 1. 원인

- 브라우저는 **HTTPS** 페이지에서 **wss://lumen.ai.kr/ws** 로 연결을 시도합니다.
- EC2에서 **nginx**(또는 Caddy 등)가 443을 받아서 백엔드(uvicorn, 포트 8000)로 넘길 때:
  - 일반 HTTP 요청은 프록시되지만
  - **WebSocket**은 `Upgrade: websocket`, `Connection: Upgrade` 헤더로 **연결 업그레이드**가 필요합니다.
- 프록시에 **WebSocket 업그레이드 설정**이 없으면 `/ws` 요청이 400/502로 끊기거나 연결이 실패합니다.

---

## 2. 해결: nginx에서 /ws 프록시 설정

EC2에서 **nginx**를 쓰는 경우, 아래처럼 **`/ws` 경로만 별도 location**으로 두고 **프록시 업그레이드**를 켜야 합니다.

### 2.1 사이트 설정 예시 (HTTPS + WebSocket)

도메인: `lumen.ai.kr`, 백엔드: `127.0.0.1:8000` (uvicorn) 이라고 가정합니다.

```nginx
server {
    listen 443 ssl;
    server_name lumen.ai.kr;

    # SSL 인증서 (Let's Encrypt 등)
    ssl_certificate     /etc/letsencrypt/live/lumen.ai.kr/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/lumen.ai.kr/privkey.pem;

    # WebSocket: /ws 만 백엔드로 업그레이드 전달 (실시간 자막·알림 필수)
    location /ws {
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;
        proxy_pass http://127.0.0.1:8000;
    }

    # 나머지(/, /auth, /api, /static 등) 일반 HTTP 프록시
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 2.2 반드시 넣을 항목 정리

| 항목 | 의미 |
|------|------|
| `proxy_http_version 1.1` | WebSocket 업그레이드에 필요 |
| `proxy_set_header Upgrade $http_upgrade` | 클라이언트의 Upgrade 헤더를 백엔드로 전달 |
| `proxy_set_header Connection "upgrade"` | Connection: upgrade 전달 |
| `proxy_read_timeout 86400` | WS 연결이 오래 유지되도록 타임아웃 길게 (선택이지만 권장) |
| `proxy_pass http://127.0.0.1:8000` | uvicorn 주소·포트에 맞게 설정 |

`/ws` **location**을 **`location /` 보다 위**에 두는 것이 좋습니다 (더 구체적인 경로를 먼저 매칭).

레포에 **`Docs/nginx-lumen-ec2.conf.example`** 예시 파일이 있으니, EC2에 복사한 뒤 SSL 경로만 수정해 사용하면 됩니다.

### 2.3 적용 방법

```bash
# 설정 파일 편집 (경로는 환경에 맞게)
sudo nano /etc/nginx/sites-available/lumen.ai.kr

# 문법 검사
sudo nginx -t

# nginx 재시작
sudo systemctl reload nginx
```

재시작 후 브라우저에서 `https://lumen.ai.kr` 접속 → 개발자 도구(F12) → **Console**에서 "WebSocket connection to 'wss://lumen.ai.kr/ws' failed" 가 사라지고, **Network → WS** 탭에서 `/ws` 가 **101 Switching Protocols** 로 연결되는지 확인하면 됩니다.

---

## 3. Caddy 사용 시

Caddy는 WebSocket를 자동으로 처리하는 경우가 많지만, 백엔드가 `http://127.0.0.1:8000` 일 때 예시는 다음과 같습니다.

```caddy
lumen.ai.kr {
    reverse_proxy /ws http://127.0.0.1:8000
    reverse_proxy http://127.0.0.1:8000
}
```

문제가 있으면 `reverse_proxy`에 `header_up Connection {http.request.header.Connection}` 등으로 업그레이드 헤더를 넘기도록 조정할 수 있습니다.

---

## 4. 체크리스트

| # | 확인 항목 |
|---|-----------|
| 1 | nginx(또는 사용 중인 프록시)에 **`/ws` 전용 location**이 있고, **Upgrade / Connection** 헤더가 백엔드로 전달되는지 |
| 2 | uvicorn이 **`--host 0.0.0.0 --port 8000`** 로 떠 있어서, 같은 서버의 nginx가 `http://127.0.0.1:8000`으로 접근 가능한지 |
| 3 | 브라우저에서 **https://lumen.ai.kr** 접속 후 F12 → Network → WS 에서 **/ws** 가 **101** 로 연결되는지 |
| 4 | EC2 보안 그룹에서 **443(HTTPS)** 인바운드가 열려 있는지 (80만 열고 443이 없으면 wss도 실패할 수 있음) |

위를 모두 적용하면 로컬과 동일하게 도메인에서도 **실시간 자막·소리 감지**가 동작합니다.
