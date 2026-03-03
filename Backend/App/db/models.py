"""ERD 기준 테이블 모델 (underdog_2.erd)."""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
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


class CustomSound(Base):
    __tablename__ = "custom_sounds"

    custom_sound_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.user_id"), nullable=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    group_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    match_target: Mapped[str | None] = mapped_column(String(255), nullable=True)
    audio_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


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

    feedback_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.event_id"))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.user_id"), nullable=True)
    client_session_uuid: Mapped[str | None] = mapped_column(String(255), nullable=True)
    vote: Mapped[str | None] = mapped_column(String(16), nullable=True)
    comment: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
