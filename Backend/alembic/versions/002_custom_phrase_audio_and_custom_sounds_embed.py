"""custom_phrase_audio 테이블 생성 + custom_sounds에 embedding 컬럼 추가

Revision ID: 002
Revises: 001
Create Date: custom_phrase_audio, custom_sounds embed columns

- custom_phrase_audio 테이블 신규 생성
- custom_sounds 테이블에 embed_dim, embed_blob, client_session_uuid, group_type, event_type 컬럼 없으면 추가 (SQLite)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _sqlite_table_exists(conn, table: str) -> bool:
    r = conn.execute(
        sa.text("SELECT 1 FROM sqlite_master WHERE type='table' AND name=:t"),
        {"t": table},
    )
    return r.fetchone() is not None


def _sqlite_table_has_column(conn, table: str, column: str) -> bool:
    r = conn.execute(sa.text(f"PRAGMA table_info({table})"))
    return any(row[1] == column for row in r.fetchall())


def upgrade() -> None:
    conn = op.get_bind()

    # 1) custom_phrase_audio 테이블 생성
    op.create_table(
        "custom_phrase_audio",
        sa.Column("custom_phrase_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("client_session_uuid", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("event_type", sa.String(16), nullable=False),
        sa.Column("threshold_pct", sa.Integer(), default=80, nullable=True),
        sa.Column("audio_path", sa.String(512), nullable=True),
        sa.Column("embed_dim", sa.Integer(), nullable=False),
        sa.Column("embed_blob", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("custom_phrase_id"),
    )
    op.create_index(
        "ix_custom_phrase_audio_client_session_uuid",
        "custom_phrase_audio",
        ["client_session_uuid"],
        unique=False,
    )

    # 2) custom_sounds에 embedding/세션 컬럼 없으면 추가 (SQLite, 테이블 있을 때만)
    if conn.dialect.name == "sqlite" and _sqlite_table_exists(conn, "custom_sounds"):
        for col_name, col_type in (
            ("client_session_uuid", "VARCHAR(255)"),
            ("group_type", "VARCHAR(32)"),
            ("event_type", "VARCHAR(32)"),
            ("embed_dim", "INTEGER"),
            ("embed_blob", "BLOB"),
        ):
            if not _sqlite_table_has_column(conn, "custom_sounds", col_name):
                op.execute(
                    sa.text(
                        f"ALTER TABLE custom_sounds ADD COLUMN {col_name} {col_type}"
                    )
                )


def downgrade() -> None:
    op.drop_index(
        "ix_custom_phrase_audio_client_session_uuid",
        table_name="custom_phrase_audio",
    )
    op.drop_table("custom_phrase_audio")
    # custom_sounds 추가 컬럼은 데이터 보존 위해 제거하지 않음
