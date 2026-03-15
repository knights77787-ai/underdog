# 프론트엔드 테스트 방법

백엔드가 **프론트 HTML/정적 파일까지 서빙**하므로, 서버 하나만 켜고 브라우저로 바로 확인할 수 있습니다.

---

## 1. 서버 실행

**프로젝트 루트(underdog)**에서 Backend 폴더로 이동한 뒤 uvicorn으로 실행합니다.

```bash
cd Backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

- `--reload`: 코드 수정 시 자동 재시작 (개발 시 편함)
- `--host 0.0.0.0`: 같은 네트워크 다른 기기에서도 접속 가능 (로컬만 쓸 땐 `127.0.0.1`만 써도 됨)
- **포트 8000**이 기본이므로 프론트에서 `http://127.0.0.1:8000`으로 API/WS 호출

실행이 되면 터미널에 `Uvicorn running on http://0.0.0.0:8000` 같은 메시지가 뜹니다.

---

## 2. 프론트 페이지 URL (백엔드가 서빙)

| URL | 페이지 |
|-----|--------|
| http://127.0.0.1:8000/ | 라이브 메인 (index.html) |
| http://127.0.0.1:8000/login | 로그인 (게스트/구글/카카오) |
| http://127.0.0.1:8000/live | 라이브와 동일 (OAuth 콜백 리다이렉트용) |

정적 파일(CSS/JS)은 `/static/...` 로 서빙됩니다 (예: `/static/js/live.js`).

### Android 에뮬레이터에서 테스트

**방법 A: adb reverse + localhost (마이크 사용 시 권장)**

`10.0.2.2`는 secure-origin이 아니라서 `navigator.mediaDevices`가 비어있거나 막힐 수 있습니다.  
마이크(실시간 자막)를 쓰려면 아래처럼 **localhost**로 접속하세요.

```bash
adb reverse tcp:8000 tcp:8000
```

그 다음 에뮬레이터 Chrome에서 **http://localhost:8000** 으로 접속.

**방법 B: 10.0.2.2 (마이크 없이 API/Connect만 테스트)**

1. 서버를 `--host 0.0.0.0` 으로 실행 (위와 동일)
2. 에뮬레이터 브라우저에서 **http://10.0.2.2:8000/** 접속
3. config.js가 현재 페이지 origin을 사용하므로 API/WS가 자동으로 `10.0.2.2`로 연결됨
4. ⚠️ `10.0.2.2`에서는 `getUserMedia`(마이크)가 동작하지 않을 수 있음

**마이크 안 될 때 디버깅:** 브라우저 콘솔에 아래 입력 후 확인
```javascript
console.log("origin:", location.origin);
console.log("mediaDevices:", navigator.mediaDevices);
```
- `mediaDevices`가 `undefined` → (A) 10.0.2.2 주소/보안 문제 (adb reverse + localhost 사용) 또는 (B) WebView 환경
- 값은 있는데 `getUserMedia`만 없음 → 구형 브라우저/특수 환경

**Google OAuth (에뮬레이터):** Google은 `10.0.2.2` 같은 IP를 redirect URI로 허용하지 않습니다.  
에뮬레이터에서 구글 로그인을 쓰려면 **ngrok**으로 공개 URL을 만들어 사용하세요. → `Frontend/OAUTH_EMULATOR.md` 참고

---

## 3. 테스트 순서

### 3.1 로그인 → 라이브 진입

1. 브라우저에서 **http://127.0.0.1:8000/login** 접속
2. **「게스트로 시작」** 클릭
3. `/?session_id=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` 형태로 **라이브 메인(/)으로 이동**하는지 확인
4. 상단에 **「세션: xxxxxxxx…」** 같은 표시가 나오는지 확인

### 3.2 세션 없이 라이브 접속 후 Connect

1. **http://127.0.0.1:8000/** 로 직접 접속 (쿼리 없이)
2. **「Connect」** 클릭
3. 서버에서 게스트 세션을 발급해 URL이 **`/?session_id=...`** 로 바뀌고, **「세션: …」** 이 보이는지 확인
4. 배지가 **「Connected」** 로 바뀌는지 확인

### 3.3 피드백 (맞아요/아니에요)

1. 라이브에서 **Connect** 한 상태로 둠
2. **알림이 한 번도 오기 전**에 **「맞아요」** 또는 **「아니에요」** 클릭  
   → **「대상 알림이 없습니다. 알림이 온 뒤에 눌러주세요.»** 토스트가 나오면 정상
3. 알림을 한 번 받은 뒤 테스트하는 방법:
   - **방법 A**: 실제로 마이크에 "불이야" 등 말해서 키워드 알림이 오게 하거나,
   - **방법 B**: 터미널/Postman으로 **POST http://127.0.0.1:8000/admin/demo/emit** 호출 (데모 알림 1건 발생)
4. 알림이 온 뒤 **「맞아요」** 클릭 → **「저장되었습니다.»** 토스트
5. (선택) **GET http://127.0.0.1:8000/admin/feedback-summary** 또는 DB에서 피드백 저장 여부 확인

### 3.4 구글/카카오 로그인 (선택)

- 서버에 `GOOGLE_CLIENT_ID`, `GOOGLE_REDIRECT_URI` 등이 설정되어 있어야 함
- 로그인 페이지에서 **Google로 로그인** / **카카오로 로그인** 클릭 → 각 OAuth 화면으로 이동
- 로그인 완료 후 **`/?session_id=...&provider=google`** (또는 kakao) 로 돌아오면 성공
- 그 상태에서 **Connect** 하면 해당 `session_id` 로 join 됨

---

## 4. 문제 나올 때

| 증상 | 확인할 것 |
|------|------------|
| 로그인 페이지가 안 뜸 / 404 | Backend에서 `app/main.py` 에 프론트 서빙 라우트(`/`, `/login`, `/live`, `/static`)가 들어가 있는지 확인 |
| CSS/JS가 안 불러와짐 | 주소창이 `http://127.0.0.1:8000/...` 인지 확인. 프론트를 다른 포트에서 열면 API_BASE/WS 주소가 달라져서 CORS/연결 오류 가능 |
| Connect 시 세션 발급 실패 | 브라우저 개발자 도구(F12) → Network에서 `POST /auth/guest` 요청/응답 확인. 백엔드 로그에 500 등 없는지 확인 |
| 피드백 "저장되었습니다" 안 나옴 | F12 → Network에서 `POST /feedback` 요청이 가는지, 응답이 200인지 확인. alert에 `event_id`가 있어야 함 (백엔드가 브로드캐스트에 event_id 포함하는지 확인) |

---

## 5. 한 줄 요약

```text
cd Backend && uvicorn main:app --reload --port 8000
```

이후 브라우저에서 **http://127.0.0.1:8000/login** → 게스트로 시작 → 라이브에서 Connect → (데모 emit 또는 말하기로 알림 발생) → 맞아요/아니에요 로 피드백 저장까지 확인하면 됩니다.
