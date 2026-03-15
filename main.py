"""
레포 루트 진입점: Render 등에서 cd Backend 없이 uvicorn main:app 으로 실행할 때 사용.
실제 앱은 Backend.App.main 에 있음.
"""
from Backend.App.main import app
