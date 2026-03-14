# Render 서버 + 구매 도메인 연결 가이드

Render에서 웹 서비스를 만들었고, 별도로 구매한 도메인을 연결하는 방법입니다.

---

## 1. Render에서 커스텀 도메인 추가

1. **Render 대시보드** → 해당 **Web Service** 선택
2. **Settings** 탭 → **Custom Domains** 섹션
3. **Add Custom Domain** 클릭
4. 구매한 도메인 입력:
   - **루트 도메인**: `yourdomain.com`
   - **서브도메인**: `www.yourdomain.com` 또는 `app.yourdomain.com` 등
5. 추가하면 Render가 **어떤 DNS 레코드를 넣으라고 할지** 안내합니다. (예: CNAME 또는 A 레코드)

---

## 2. 도메인 판매처(DNS)에서 레코드 설정

도메인을 구매한 곳(가비아, 카페24, Cloudflare, Namecheap 등)의 **DNS 관리** 메뉴로 들어갑니다.

### 서브도메인만 쓸 때 (예: www.yourdomain.com, app.yourdomain.com)

| 타입 | 이름 (호스트) | 값 (가리킬 주소) |
|------|----------------|-------------------|
| **CNAME** | `www` 또는 `app` | Render가 알려준 주소 (예: `underdog-xxxx.onrender.com`) |

- 이름에 `www` 넣으면 → `www.yourdomain.com` 이 Render로 연결
- 이름에 `app` 넣으면 → `app.yourdomain.com` 이 Render로 연결

### 루트 도메인 (yourdomain.com) 쓸 때

DNS 업체에 따라 다릅니다.

- **A 레코드**:  
  - 이름: `@` (또는 비움)  
  - 값: `216.24.57.1` (Render 공식 IP)
- **ANAME/ALIAS**를 지원하면:  
  - 루트를 Render 서비스 주소(예: `xxx.onrender.com`)로 연결

Render 안내에 나온 대로만 넣으면 됩니다.

### 주의

- **AAAA(IPv6) 레코드**가 있으면 제거하는 것이 좋습니다. Render는 IPv4만 사용합니다.
- DNS 반영은 **몇 분~최대 48시간** 걸릴 수 있습니다.

---

## 3. Render 환경 변수 (Environment Variables)

배포된 **실제 접속 주소**를 쓰도록 다음을 설정합니다.

| 이름 | 값 | 비고 |
|------|-----|------|
| `LOG_LEVEL` | `INFO` | 로그 레벨 |
| `FRONTEND_AUTH_REDIRECT_URL` | `https://yourdomain.com/live` 또는 `/live` | OAuth 로그인 후 돌아갈 주소. **절대 URL**로 넣으면 그대로 사용되고, `/live`처럼 **상대 경로**면 현재 요청 Host(도메인)가 붙음 |
| `ADMIN_TOKEN` | (비밀값) | 관리자 인증용 |
| `GOOGLE_CLIENT_ID` | (Google 콘솔 값) | .env와 동일 |
| `GOOGLE_CLIENT_SECRET` | (Google 콘솔 값) | .env와 동일 |
| `KAKAO_CLIENT_ID` | (Kakao 값) | .env와 동일 |
| `KAKAO_CLIENT_SECRET` | (Kakao 값) | .env와 동일 |

- 도메인을 **한 개만** 쓴다면 `FRONTEND_AUTH_REDIRECT_URL=/live` 로 두고, 사용자가 접속하는 주소가 `https://yourdomain.com` 이면 자동으로 `https://yourdomain.com/live` 로 리다이렉트됩니다.
- **DEV** 변수는 배포 환경에서는 넣지 않거나 `0`으로 두세요.

---

## 4. Google / Kakao OAuth 콘솔에 배포 URL 등록

OAuth 로그인은 **리다이렉트 URL이 콘솔에 등록된 것만** 허용합니다. 배포 도메인을 반드시 추가해야 합니다.

### Google Cloud Console

1. [Google Cloud Console](https://console.cloud.google.com/) → 사용 중인 프로젝트
2. **APIs & Services** → **Credentials** → 사용하는 OAuth 2.0 클라이언트 ID
3. **Authorized redirect URIs**에 추가:
   - `https://yourdomain.com/auth/google/callback`
   - (www 쓴다면) `https://www.yourdomain.com/auth/google/callback`
4. **Authorized JavaScript origins**에도 동일하게:
   - `https://yourdomain.com`
   - `https://www.yourdomain.com` (사용하는 경우)
5. 저장

### Kakao Developers

1. [Kakao Developers](https://developers.kakao.com/) → 해당 앱
2. **앱 설정** → **플랫폼** → **Web** (이미 있으면 수정)
3. **Redirect URI**에 추가:
   - `https://yourdomain.com/auth/kakao/callback`
   - (www 쓴다면) `https://www.yourdomain.com/auth/kakao/callback`
4. 저장

여기서 `yourdomain.com` 은 실제 구매한 도메인으로 바꾸면 됩니다.

---

## 5. 연결 확인 순서

1. DNS 설정 저장 후 5~10분 뒤 **Render 대시보드 → Custom Domains**에서 인증서/상태가 정상인지 확인
2. 브라우저에서 `https://yourdomain.com` 접속
3. 로그인(Google/Kakao) 시도 → 리다이렉트 후 `/live` 로 잘 돌아오는지 확인

문제가 있으면:

- DNS 전파: [dnschecker.org](https://dnschecker.org) 에서 해당 도메인 CNAME/A 조회
- Render 로그: 서비스 **Logs** 탭에서 에러 메시지 확인
- OAuth: redirect_uri 불일치 에러 시 위 4번의 URL이 콘솔에 **완전히 동일하게** 등록됐는지 확인

---

## 요약

| 단계 | 할 일 |
|------|--------|
| 1 | Render 서비스에 Custom Domain 추가 후, 안내된 DNS 타입/이름/값 확인 |
| 2 | 도메인 구매처 DNS에 CNAME(또는 A/ANAME) 레코드 추가 |
| 3 | Render Environment Variables에 `.env` 값 이식 + `FRONTEND_AUTH_REDIRECT_URL` 필요 시 절대 URL로 설정 |
| 4 | Google / Kakao 콘솔에 `https://(도메인)/auth/.../callback` 등록 |
| 5 | 브라우저로 접속·로그인 테스트 |

이 순서대로 하면 서버(Render)와 구매 도메인 연결이 완료됩니다.

---

## api.lumen.ai.kr 사용 시: 프로젝트와 연결

이 프로젝트는 **백엔드 한 서비스가 API + 프론트(HTML/JS)를 같이 서빙**합니다.  
사용자가 `https://api.lumen.ai.kr` 로 접속하면 같은 도메인에서 API·WebSocket이 동작하고, `Frontend/static/js/config.js` 가 `document.location.origin` 을 쓰므로 **별도 코드 수정 없이** API/WS 주소가 `https://api.lumen.ai.kr`, `wss://api.lumen.ai.kr/ws` 로 잡힙니다.

### 해야 할 것 (도메인 연결 후)

| 순서 | 할 일 |
|------|--------|
| 1 | **Render Environment Variables**에 `.env` 값 넣기 (LOG_LEVEL, FRONTEND_AUTH_REDIRECT_URL, ADMIN_TOKEN, GOOGLE_*, KAKAO_*). `FRONTEND_AUTH_REDIRECT_URL` 는 `/live` 만 넣어도 됨 (같은 도메인 사용 시). |
| 2 | **Google Cloud Console** → Credentials → OAuth 2.0 클라이언트에서 **Authorized redirect URIs**에 `https://api.lumen.ai.kr/auth/google/callback` 추가, **Authorized JavaScript origins**에 `https://api.lumen.ai.kr` 추가 후 저장. |
| 3 | **Kakao Developers** → 앱 설정 → Web 플랫폼 **Redirect URI**에 `https://api.lumen.ai.kr/auth/kakao/callback` 추가 후 저장. |
| 4 | 브라우저에서 `https://api.lumen.ai.kr` 접속 → 로그인(Google/Kakao) → `/live` 로 돌아오는지 확인. |

위만 하면 **도메인과 우리가 작업한 프로젝트 연결**이 끝납니다.
