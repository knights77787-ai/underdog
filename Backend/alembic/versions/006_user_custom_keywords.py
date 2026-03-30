"""user_custom_keywords table for STT keyword registration

Revision ID: 006
Revises: 005
Create Date: 2026-03-30
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _sqlite_table_exists(conn, name: str) -> bool:
    r = conn.execute(sa.text("SELECT name FROM sqlite_master WHERE type='table' AND name=:n"), {"n": name})
    return r.fetchone() is not None


def upgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "sqlite":
        if _sqlite_table_exists(conn, "user_custom_keywords"):
            return
    op.create_table(
        "user_custom_keywords",
        sa.Column("user_custom_keyword_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("client_session_uuid", sa.String(length=255), nullable=True),
        sa.Column("phrase", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("user_custom_keyword_id"),
    )
    op.create_index(
        op.f("ix_user_custom_keywords_client_session_uuid"),
        "user_custom_keywords",
        ["client_session_uuid"],
        unique=False,
    )
    op.create_index(
        op.f("ix_user_custom_keywords_user_id"),
        "user_custom_keywords",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_user_custom_keywords_user_id"), table_name="user_custom_keywords")
    op.drop_index(op.f("ix_user_custom_keywords_client_session_uuid"), table_name="user_custom_keywords")
    op.drop_table("user_custom_keywords")
