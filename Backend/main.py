# App 폴더의 FastAPI 앱을 진입점으로 노출 (uvicorn main:app 시 사용)
# Render(Linux)는 대소문자 구분 → App (대문자)로 통일해야 함.
from App.main import app