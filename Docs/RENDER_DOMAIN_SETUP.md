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
| `OPENAI_API_KEY` | (선택) OpenAI API 키 | 설정 시 STT를 로컬 Whisper 대신 OpenAI Whisper API로 사용 → 서버 메모리 절감. 없으면 로컬 모델 사용. |

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

## lumen.ai.kr 사용 시 (EC2): 프로젝트와 연결

이 프로젝트는 **백엔드 한 서비스가 API + 프론트(HTML/JS)를 같이 서빙**합니다.  
사용자가 `https://lumen.ai.kr` 로 접속하면 같은 도메인에서 API·WebSocket이 동작하고, `Frontend/static/js/config.js` 가 `document.location.origin` 을 쓰므로 API/WS 주소가 `https://lumen.ai.kr`, `wss://lumen.ai.kr/ws` 로 잡힙니다.

### EC2 탄력적 IP (DNS A 레코드용)

| 항목 | 값 |
|------|-----|
| **EC2 탄력적 IP** | `52.79.135.6` |
| **DNS A 레코드** | 도메인 `lumen.ai.kr`(또는 `@`) → 값 `52.79.135.6` |

도메인 구매처 DNS에서 **A 레코드**로 위 IP를 넣어 두면 `https://lumen.ai.kr` 이 해당 EC2 인스턴스로 연결됩니다.  
프론트엔드 `config.js` 에 동일 IP가 반영되어 있어, 도메인 없이 `http://52.79.135.6:8000` 으로 접속해도 API/WS가 같은 호스트로 동작합니다.

### 해야 할 것 (도메인 연결 후)

| 순서 | 할 일 |
|------|--------|
| 1 | **EC2(또는 배포 환경) 환경 변수**에 `.env` 값 넣기 (LOG_LEVEL, FRONTEND_AUTH_REDIRECT_URL, ADMIN_TOKEN, GOOGLE_*, KAKAO_*). `FRONTEND_AUTH_REDIRECT_URL` 는 `/live` 만 넣어도 됨 (같은 도메인 사용 시). |
| 2 | **Google Cloud Console** → Credentials → OAuth 2.0 클라이언트에서 **Authorized redirect URIs**에 `https://lumen.ai.kr/auth/google/callback` 추가, **Authorized JavaScript origins**에 `https://lumen.ai.kr` 추가 후 저장. |
| 3 | **Kakao Developers** → 앱 설정 → Web 플랫폼 **Redirect URI**에 `https://lumen.ai.kr/auth/kakao/callback` 추가 후 저장. |
| 4 | 브라우저에서 `https://lumen.ai.kr` 접속 → 로그인(Google/Kakao) → `/live` 로 돌아오는지 확인. |
| 5 | **도메인에서 실시간 자막/소리 감지가 안 되고** 콘솔에 "WebSocket connection to 'wss://lumen.ai.kr/ws' failed" 가 뜨면 → **`Docs/EC2_WEBSOCKET_SETUP.md`** 참고. nginx(또는 사용 중인 프록시)에서 **/ws** 경로를 백엔드로 **WebSocket 업그레이드**해 주어야 합니다. |

위만 하면 **도메인과 우리가 작업한 프로젝트 연결**이 끝납니다.

### EC2에서 로그인(OAuth)이 500/503일 때

**증상:** Google/카카오 로그인 클릭 시 "Google OAuth is not configured for this app" 또는 500/503 에러.

**원인:** EC2 서버에서 **GOOGLE_CLIENT_ID**, **GOOGLE_CLIENT_SECRET**, **KAKAO_CLIENT_ID**(, **KAKAO_CLIENT_SECRET**) 환경 변수가 로드되지 않음.  
앱은 **프로젝트 루트(underdog)** 또는 **Backend** 폴더의 **`.env`** 파일을 기동 시 자동 로드합니다. EC2에 `.env`를 두지 않았거나, 다른 디렉터리에서 실행해 경로가 어긋나면 변수가 비어 있습니다.

**해결:**
1. 로컬의 **`.env`** 파일을 EC2 서버로 복사합니다. (예: `scp .env ubuntu@52.79.135.6:~/underdog/.env`)
2. **프로젝트 루트**에서 uvicorn을 실행 중이라면 `.env`를 **루트**에 두고, **Backend** 안에서만 실행한다면 **Backend/.env**에 둡니다.
3. 앱을 **재시작**한 뒤 다시 로그인을 시도합니다.
4. 서버 기동 시 터미널에 `WARNING: GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET not set` 가 뜨면 아직 `.env`가 로드되지 않은 것이므로, 위 경로를 확인하세요.

(코드에서는 OAuth 미설정 시 브라우저에는 안내 HTML, API에는 503 + 메시지를 반환하도록 되어 있습니다.)

### EC2에서 도메인 사용 시 WebSocket(wss) 필수

로컬(`127.0.0.1:8000`)에서는 잘 되는데 **도메인(`https://lumen.ai.kr`)에서만** 자막 인식이 안 되고 콘솔에 WebSocket 에러가 많이 뜨는 경우, **리버스 프록시가 `/ws` 를 백엔드로 업그레이드 전달하지 않아서**입니다.  
→ **`Docs/EC2_WEBSOCKET_SETUP.md`** 에 nginx 설정 예시와 체크리스트가 있으니 그대로 적용하면 됩니다.

### Render Build/Start (Root Directory 비울 때)

Root Directory를 **비우고** 레포 루트에서 배포할 때는 아래처럼 맞추세요.

| 항목 | 값 |
|------|-----|
| **Root Directory** | *(비움)* |
| **Build Command** | `cd Backend && pip install -r requirements.txt` |
| **Start Command** | **`cd Backend && uvicorn App.main:app --host 0.0.0.0 --port $PORT`** (권장) |
| **Pre-Deploy Command** | *(비움)* |

- **반드시 `cd Backend && uvicorn App.main:app ...` 사용:** Render(Linux)는 대소문자 구분. **Backend** 를 작업 디렉터리로 두고 **`App.main:app`** 으로 실행합니다.
- Build Command는 그대로 **`cd Backend && pip install -r requirements.txt`** (의존성은 Backend 기준).
- **배포 전:** Backend에서 `python scripts/check_requirements.py` 를 실행하면, 코드에서 쓰는 `import` 와 `requirements.txt` 를 비교해 누락된 패키지가 있으면 알려줍니다. 새 라이브러리 추가 후 배포 전에 한 번 돌려보면 좋습니다.
- 포트는 **`$PORT`** 로 두세요 (10000 고정 금지).

### 가벼운 기동 (OOM 방지)

Render 등 메모리 제한 환경에서 **Out of memory** 가 나면, 기동 시 Yamnet/STT 워커와 `reload_audio_rules` 를 건너뛰도록 되어 있습니다.

- **기본(권장):** `ENABLE_ML_WORKERS` 를 **설정하지 않음** → 워커 없이 기동. `/`, `/docs`, `/openapi.json` 등 REST는 정상 동작.
- **ML 워커 켜기:** 환경 변수에 `ENABLE_ML_WORKERS=1` 추가 후 재배포 → Yamnet·STT 워커와 오디오 룰 로드 수행 (메모리 사용 증가). 인스턴스 메모리 권장치는 아래 참고.

### ML 워커 켰을 때 메모리 (정상 동작 최소 사양)

이 프로젝트에서 쓰는 모델·워커 기준 대략 사용량은 다음과 같습니다.

| 항목 | 대략 메모리 |
|------|-------------|
| Whisper **small** (STT, 1개) | ~1GB |
| Whisper **base** (PHRASE_EMB, 구문 임베딩) | ~400MB |
| Yamnet (오디오 분류, TFHub) | ~300MB |
| PyTorch / TensorFlow 런타임 | ~500MB~1GB |
| Python + FastAPI + 기타 | ~300~500MB |
| **합계(대략)** | **약 2.5~4GB** |

- **2GB:** 이전에 “used over 2Gi” OOM 이 났으므로 **부족**. ML 워커 켜면 비추.
- **최소 권장:** **4GB** (ML 워커 켠 상태로 기동·동작 목표).
- **여유 있게:** **8GB** (동시 접속·피크 시에도 여유 두고 쓰기 좋음).

Render에서 플랜을 올릴 때 위 용량을 참고해 인스턴스 메모리를 선택하면 됩니다.

### Whisper API로 STT 시 메모리 절감 (권장)

STT(음성→텍스트)를 **로컬 Whisper 모델** 대신 **OpenAI Whisper API** 로 돌리면, 서버에서 Whisper 모델을 로드하지 않아 **메모리 약 1GB 이상 절감**됩니다.

- **설정 방법:** Render(또는 로컬) **Environment Variables** 에 `OPENAI_API_KEY` 를 넣어 두면, 앱이 자동으로 API 방식으로 STT를 사용합니다.
- **동작:** `OPENAI_API_KEY` 필수 → `WhisperAPISTT` (OpenAI Whisper API 호출). 키 없으면 STT 비활성화.
- **비용:** OpenAI 사용량에 따라 과금됩니다. [OpenAI 가격](https://openai.com/api/pricing/) 참고.
- **효과:** API 사용 시 로컬 Whisper 미로드 → ML 워커 켠 상태에서도 **최소 권장 메모리를 4GB → 약 2.5~3GB 수준**으로 낮출 수 있습니다.

### Python 버전 및 TensorFlow (ModuleNotFoundError 방지)

Render 기본 Python이 3.14 등일 수 있고, **TensorFlow는 3.10–3.12** 지원이므로 호환되지 않으면 `ModuleNotFoundError: No module named 'tensorflow'` 또는 설치 실패가 납니다.

- **권장:** Python **3.12** 사용.
  - **방법 A:** Render **Environment Variables** 에 `PYTHON_VERSION=3.12.11` 추가.
  - **방법 B:** 레포 루트에 **`.python-version`** 파일 추가, 내용 `3.12` (이미 추가됨).
- **의존성:** `Backend/requirements.txt` 에 `tensorflow>=2.15.0` 포함됨. CPU만 쓰면 `tensorflow` 만 있으면 됨.
- **메모리:** `custom_phrase_audio.py` 에서 TensorFlow는 **해당 API(커스텀 구문 오디오 업로드) 호출 시에만** 지연 로드하므로, 앱 기동 시에는 TensorFlow가 로드되지 않아 메모리 부담이 줄어듦.
