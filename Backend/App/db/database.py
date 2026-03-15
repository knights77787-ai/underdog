"""SQLite 엔진 및 세션. 앱 기동 시 테이블 생성."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.Core.config import DATABASE_PATH, SQLITE_URL
from app.db.models import Base

DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    SQLITE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def create_tables() -> None:
    """모든 테이블 생성 (없을 때만)."""
    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI Depends용."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
