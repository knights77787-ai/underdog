# Render 서버 연결 실패 요인 정리

Render 배포 시 서버가 뜨지 않았던 원인과 해결을 정리한 문서입니다.

---

## 1. 모듈 대소문자 (App vs app)

**증상:** `ModuleNotFoundError: No module named 'app'`

**원인**
- Render 서버는 **Linux**라서 폴더/모듈 이름의 **대소문자를 구분**합니다.
- Git에는 `Backend/App/`(대문자 A)로 올라가 있으므로, 코드에서도 `from App.main import app` 같이 **App**(대문자)을 사용해야 Linux에서 정상 동작합니다.

**해결**
- `Backend/main.py`: **`from App.main import app`** (대문자 `App`) 사용.
- `Backend/App/` 안의 모든 파일: `from App.xxx`, `import App.xxx` 형태로 통일.
- **Start Command**의 `main:app`은 그대로 둡니다. `main`은 `Backend/main.py` 파일을 가리키는 것이고, 그 안에서 `App` 패키지를 import합니다.

**참고:** 로컬(Windows)은 대소문자를 구분하지 않아서 `app`/`App` 둘 다 동작할 수 있지만, Render에서는 반드시 Git에 올라간 폴더 이름(`App`)과 import를 맞춰야 합니다.

---

## 2. Root Directory와 Start Command 불일치

**증상:** 앱이 기동하지 않거나, "Could not import module 'main'" 같은 오류.

**원인**
- **Root Directory**를 `Backend`로 두었는데 Start Command에 `cd Backend`가 있으면, 실제 작업 디렉터리가 `Backend/Backend`가 되어 `main.py`를 찾지 못합니다.

**해결**
- **Root Directory를 비울 때:**  
  Start Command: `cd Backend && uvicorn main:app --host 0.0.0.0 --port $PORT`
- **Root Directory를 `Backend`로 둘 때:**  
  Start Command에서 `cd Backend` 제거 → `uvicorn main:app --host 0.0.0.0 --port $PORT` 만 사용.

---

## 3. 포트를 고정값으로 설정

**증상:** "No open ports detected", 서비스가 정상 바인딩되지 않음.

**원인**
- Render는 실행 시 **`$PORT`** 환경 변수로 포트를 알려줍니다. 여기에 바인딩해야 합니다.
- `--port 10000`처럼 고정 포트를 쓰면 Render가 해당 프로세스를 웹 서비스로 인식하지 못합니다.

**해결**
- Start Command에서 반드시 **`--port $PORT`** 사용.

---

## 4. requirements.txt에 누락된 패키지

**증상:** `ModuleNotFoundError: No module named 'xxx'` (예: `tensorflow_hub`, `scipy`)

**원인**
- 코드에서는 `import tensorflow_hub`, `from scipy.signal import resample` 등을 쓰는데, 해당 패키지가 `Backend/requirements.txt`에 없으면 빌드 시 설치되지 않습니다.
- 로컬에는 이미 설치돼 있어서 문제가 없었을 수 있습니다.

**해결**
- 사용하는 서드파티 패키지는 모두 `Backend/requirements.txt`에 명시.
- 이번에 추가·확인한 예:
  - `tensorflow_hub>=0.15.0` (Yamnet 서비스)
  - `scipy>=1.10.0` (custom_sounds 리샘플링)
  - `python-multipart` (폼 데이터)
- **배포 전 점검:** Backend에서 `python scripts/check_requirements.py` 실행 → 코드의 import와 requirements.txt를 비교해 누락 여부 확인.

---

## 5. Form 데이터 처리용 패키지

**증상:** `RuntimeError: Form data requires "python-multipart"`

**원인**
- FastAPI에서 폼 데이터(`Form()`)를 쓰려면 `python-multipart` 패키지가 필요합니다.

**해결**
- `Backend/requirements.txt`에 **`python-multipart>=0.0.6`** 추가.

---

## 6. 루트 경로(/) 404

**증상:** `https://lumen.ai.kr/` 접속 시 404.

**원인**
- 루트 경로 `/`에 대한 라우트가 없거나, 정적 파일(index.html)만 있고 서버 설정이 맞지 않음.

**해결**
- `Backend/App/main.py`에서 `/` 라우트 추가: `index.html`이 있으면 그걸 서빙, 없으면 `/docs`로 리다이렉트.

---

## 7. 환경 변수 미설정

**증상:** 로그인 실패, API 오류, 또는 앱이 기대한 설정을 못 찾음.

**원인**
- `.env`는 Git에 올리지 않고, Render에서는 **Environment Variables**에 따로 넣어야 합니다.

**해결**
- Render 대시보드 → 해당 Web Service → **Environment** 탭에서 로컬 `.env`와 동일한 변수 설정.
- 예: `ADMIN_TOKEN`, `GOOGLE_*`, `KAKAO_*`, `OPENAI_API_KEY`, `FRONTEND_AUTH_REDIRECT_URL`, `LOG_LEVEL`, `ENABLE_ML_WORKERS` 등.
- OAuth는 **리다이렉트 URL**을 배포 도메인(예: `https://lumen.ai.kr`)으로 Google/Kakao 콘솔에 등록해야 합니다.

---

## 8. OOM(메모리 부족)

**증상:** 배포 중 또는 기동 직후 "Exited with status 137", "used over 2Gi" 등 메모리 관련 오류.

**원인**
- Yamnet, Whisper, TensorFlow 등 ML 모델을 한꺼번에 로드하면 2GB 인스턴스에서는 부족할 수 있습니다.

**해결**
- **ENABLE_ML_WORKERS**를 설정하지 않으면 ML 워커를 건너뛰어 가볍게 기동.
- **OPENAI_API_KEY**를 넣으면 STT를 로컬 Whisper 대신 OpenAI Whisper API로 사용 → 서버 메모리 절감.
- ML 워커를 켤 경우 인스턴스 메모리 **최소 4GB** 권장 (상세는 `RENDER_DOMAIN_SETUP.md` 참고).

---

## 9. Python / TensorFlow 버전

**증상:** `ModuleNotFoundError: No module named 'tensorflow'` 또는 TensorFlow 설치 실패.

**원인**
- TensorFlow는 Python 3.10–3.12를 지원합니다. Render 기본이 3.14 등이면 호환되지 않을 수 있습니다.

**해결**
- **.python-version** 파일을 레포 루트에 두고 내용을 `3.12`로 설정.
- 또는 Render Environment에 `PYTHON_VERSION=3.12.11` 설정.

---

## 체크리스트 (배포 전)

| 항목 | 확인 |
|------|------|
| `Backend/main.py`가 `from App.main import app` 사용 (대문자 App) | ☐ |
| Root Directory와 Start Command의 `cd Backend` 일치 | ☐ |
| Start Command에 `--port $PORT` 사용 | ☐ |
| `python scripts/check_requirements.py` 실행 후 누락 패키지 없음 | ☐ |
| Render Environment에 필요한 환경 변수 등록 | ☐ |
| OAuth 리다이렉트 URL에 배포 도메인 등록 | ☐ |

---

*이 문서는 Render 배포 과정에서 발생했던 문제를 바탕으로 정리했습니다. 추가 이슈는 `RENDER_DOMAIN_SETUP.md`와 함께 참고하세요.*
