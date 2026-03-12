# 에뮬레이터에서 Google OAuth 사용하기

Google Cloud Console은 **IP 주소**(`10.0.2.2`, `127.0.0.1` 등)를 redirect URI로 허용하지 않습니다.  
에뮬레이터에서 구글 로그인을 쓰려면 **ngrok**으로 공개 URL을 만들어 사용해야 합니다.

---

## 방법 1: ngrok 사용 (권장)

### 1) ngrok 설치 및 실행

```bash
# ngrok 설치 (https://ngrok.com/download)
# 실행 (서버가 8000 포트에서 돌아가는 상태에서)
ngrok http 8000
```

실행하면 예시처럼 URL이 나옵니다:
```
Forwarding  https://abc123.ngrok-free.app -> http://localhost:8000
```

### 2) Google Cloud Console 설정

1. [Google Cloud Console](https://console.cloud.google.com/) → APIs & Services → Credentials
2. OAuth 2.0 클라이언트 ID 선택
3. **Authorized redirect URIs**에 추가:
   - `https://abc123.ngrok-free.app/auth/google/callback`  
     (위에서 나온 ngrok URL로 교체)

### 3) 에뮬레이터에서 접속

에뮬레이터 브라우저에서 **https://abc123.ngrok-free.app** 접속 후 구글 로그인 사용.

> **참고:** ngrok 무료 버전은 실행할 때마다 URL이 바뀝니다. URL이 바뀔 때마다 Google Console의 redirect URI를 새 URL로 수정해야 합니다.

---

## 방법 2: 에뮬레이터에서는 게스트 로그인만 사용

에뮬레이터 테스트 시에는 **게스트로 시작**만 사용하고, 구글 로그인은 PC 브라우저에서만 테스트합니다.

- PC: `http://127.0.0.1:8000` → 구글 로그인 가능
- 에뮬레이터: `http://10.0.2.2:8000` → 게스트 로그인만 사용

---

## 요약

| 환경 | 구글 로그인 | 게스트 로그인 |
|------|------------|---------------|
| PC (localhost) | ✅ | ✅ |
| 에뮬레이터 (10.0.2.2) | ❌ (Google 정책) | ✅ |
| 에뮬레이터 + ngrok | ✅ | ✅ |
