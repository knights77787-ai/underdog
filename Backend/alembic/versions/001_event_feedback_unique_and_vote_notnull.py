"""event_feedback: UniqueConstraint(event_id, client_session_uuid), vote NOT NULL

Revision ID: 001
Revises:
Create Date: event_feedback 스키마 정리

- (event_id, client_session_uuid) 유니크 제약 추가
- vote NOT NULL, String(8)
- client_session_uuid String(64)
- 기존 vote NULL → 'up' 으로 보정
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLite: 기존 테이블이 있으면 재생성, 없으면 새로 생성
    conn = op.get_bind()
    if conn.dialect.name != "sqlite":
        op.create_unique_constraint(
            "uq_feedback_event_session",
            "event_feedback",
            ["event_id", "client_session_uuid"],
        )
        op.alter_column(
            "event_feedback",
            "vote",
            existing_type=sa.String(16),
            type_=sa.String(8),
            nullable=False,
        )
        op.alter_column(
            "event_feedback",
            "client_session_uuid",
            existing_type=sa.String(255),
            type_=sa.String(64),
        )
        return

    # SQLite: 테이블 존재 여부 확인
    r = conn.execute(
        sa.text(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='event_feedback'"
        )
    ).scalar()
    if not r:
        op.create_table(
            "event_feedback",
            sa.Column("feedback_id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("event_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=True),
            sa.Column("client_session_uuid", sa.String(64), nullable=True),
            sa.Column("vote", sa.String(8), nullable=False),
            sa.Column("comment", sa.String(255), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["event_id"], ["events.event_id"]),
            sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
            sa.PrimaryKeyConstraint("feedback_id"),
            sa.UniqueConstraint(
                "event_id", "client_session_uuid", name="uq_feedback_event_session"
            ),
        )
        return

    # 기존 테이블 백업 후 재생성
    op.execute("""
        CREATE TABLE event_feedback_new (
            feedback_id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL REFERENCES events(event_id),
            user_id INTEGER REFERENCES users(user_id),
            client_session_uuid VARCHAR(64),
            vote VARCHAR(8) NOT NULL,
            comment VARCHAR(255),
            created_at DATETIME,
            CONSTRAINT uq_feedback_event_session UNIQUE (event_id, client_session_uuid)
        )
    """)
    op.execute("""
        INSERT INTO event_feedback_new
            (feedback_id, event_id, user_id, client_session_uuid, vote, comment, created_at)
        SELECT
            feedback_id,
            event_id,
            user_id,
            CASE WHEN client_session_uuid IS NULL THEN NULL
                 WHEN length(client_session_uuid) > 64 THEN substr(client_session_uuid, 1, 64)
                 ELSE client_session_uuid END,
            CASE WHEN vote IS NULL OR vote = '' THEN 'up' ELSE vote END,
            comment,
            created_at
        FROM event_feedback
    """)
    op.execute("DROP TABLE event_feedback")
    op.execute("ALTER TABLE event_feedback_new RENAME TO event_feedback")


def downgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name != "sqlite":
        op.drop_constraint(
            "uq_feedback_event_session", "event_feedback", type_="unique"
        )
        op.alter_column(
            "event_feedback",
            "vote",
            existing_type=sa.String(8),
            type_=sa.String(16),
            nullable=True,
        )
        op.alter_column(
            "event_feedback",
            "client_session_uuid",
            existing_type=sa.String(64),
            type_=sa.String(255),
        )
        return

    op.execute("""
        CREATE TABLE event_feedback_old (
            feedback_id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            user_id INTEGER,
            client_session_uuid VARCHAR(255),
            vote VARCHAR(16),
            comment VARCHAR(255),
            created_at DATETIME,
            FOREIGN KEY(event_id) REFERENCES events(event_id),
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
    """)
    op.execute("""
        INSERT INTO event_feedback_old
            (feedback_id, event_id, user_id, client_session_uuid, vote, comment, created_at)
        SELECT feedback_id, event_id, user_id, client_session_uuid, vote, comment, created_at
        FROM event_feedback
    """)
    op.execute("DROP TABLE event_feedback")
    op.execute("ALTER TABLE event_feedback_old RENAME TO event_feedback")
