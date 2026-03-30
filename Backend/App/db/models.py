"""ERD 기준 테이블 모델 (underdog_2.erd)."""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    oauth_provider: Mapped[str | None] = mapped_column(String(255), nullable=True)
    oauth_sub: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Session(Base):
    __tablename__ = "sessions"

    session_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.user_id"), nullable=True)
    is_guest: Mapped[bool] = mapped_column(Boolean, default=True)
    recording_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    client_session_uuid: Mapped[str | None] = mapped_column(String(255), nullable=True)
    start_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    end_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    events: Mapped[list["Event"]] = relationship("Event", back_populates="session")
    # 1세션=1설정 (settings 테이블과 1:1)
    settings: Mapped["SettingsModel | None"] = relationship(
        "SettingsModel", back_populates="session", uselist=False, cascade="all, delete-orphan"
    )


class SettingsModel(Base):
    """세션별 설정 1건. sessions.session_id와 1:1."""
    __tablename__ = "settings"
    __table_args__ = (UniqueConstraint("session_id", name="uq_settings_session_id"),)  # 1세션=1설정

    settings_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("sessions.session_id"), nullable=False)
    data_json: Mapped[str] = mapped_column(Text, nullable=False)  # 설정값 JSON 문자열

    session: Mapped["Session"] = relationship("Session", back_populates="settings")


class CustomSound(Base):
    __tablename__ = "custom_sounds"

    custom_sound_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.user_id"), nullable=True)
    client_session_uuid: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    event_type: Mapped[str | None] = mapped_column(String(32), nullable=True)  # "danger" | "caution" | "alert"
    match_target: Mapped[str | None] = mapped_column(String(255), nullable=True)
    audio_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    embed_dim: Mapped[int | None] = mapped_column(Integer, nullable=True)
    embed_blob: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    # 개별 커스텀 소리 임계값(없으면 전역 CUSTOM_SOUND_THRESHOLD 사용)
    match_threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class UserCustomKeyword(Base):
    """사용자가 등록한 STT 키워드(문구). 실시간 자막·알림 판정 시 기본 키워드와 병합."""

    __tablename__ = "user_custom_keywords"

    user_custom_keyword_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.user_id"), nullable=True, index=True)
    client_session_uuid: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    phrase: Mapped[str] = mapped_column(String(255), nullable=False)
    event_type: Mapped[str] = mapped_column(String(16), nullable=False)  # danger | caution | alert
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CustomPhraseAudio(Base):
    __tablename__ = "custom_phrase_audio"

    custom_phrase_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    client_session_uuid: Mapped[str] = mapped_column(String(64), index=True)

    name: Mapped[str] = mapped_column(String(255))
    event_type: Mapped[str] = mapped_column(String(16))  # "danger" | "caution" | "alert"
    threshold_pct: Mapped[int] = mapped_column(Integer, default=80)  # 80 => 0.80

    audio_path: Mapped[str | None] = mapped_column(String(512), nullable=True)

    embed_dim: Mapped[int] = mapped_column(Integer)
    embed_blob: Mapped[bytes] = mapped_column(LargeBinary)  # float32 bytes

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Event(Base):
    __tablename__ = "events"

    event_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.session_id"))
    event_type: Mapped[str] = mapped_column(String(32))
    danger_score: Mapped[float] = mapped_column(Float, default=0.0)
    alert_score: Mapped[float] = mapped_column(Float, default=0.0)
    topk_labels: Mapped[str | None] = mapped_column(Text, nullable=True)
    matched_custom_sound_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    custom_similarity: Mapped[float | None] = mapped_column(Float, nullable=True)
    # custom 판정 관측값(튜닝/분석용)
    custom_threshold_used: Mapped[float | None] = mapped_column(Float, nullable=True)
    custom_rms: Mapped[float | None] = mapped_column(Float, nullable=True)
    custom_pick_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    segment_start_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    segment_end_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vad_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    keyword: Mapped[str | None] = mapped_column(String(255), nullable=True)

    session: Mapped["Session"] = relationship("Session", back_populates="events")
    transcripts: Mapped[list["EventTranscript"]] = relationship(
        "EventTranscript", back_populates="event"
    )


class EventTranscript(Base):
    __tablename__ = "event_transcripts"

    transcript_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.event_id"))
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    event: Mapped["Event"] = relationship("Event", back_populates="transcripts")


class EventFeedback(Base):
    __tablename__ = "event_feedback"
    __table_args__ = (
        UniqueConstraint("event_id", "client_session_uuid", name="uq_feedback_event_session"),
    )

    feedback_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.event_id"), nullable=False)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.user_id"), nullable=True)
    client_session_uuid: Mapped[str | None] = mapped_column(String(64), nullable=True)
    vote: Mapped[str] = mapped_column(String(8), nullable=False)  # "up" | "down"
    comment: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DeviceToken(Base):
    __tablename__ = "device_tokens"
    __table_args__ = (
        UniqueConstraint("token", name="uq_device_tokens_token"),
    )

    device_token_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.user_id"), nullable=True)
    client_session_uuid: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    platform: Mapped[str] = mapped_column(String(16), default="android")  # android | ios | web
    token: Mapped[str] = mapped_column(String(512), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
