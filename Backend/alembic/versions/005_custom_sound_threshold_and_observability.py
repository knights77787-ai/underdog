"""custom sound per-item threshold and observability columns

Revision ID: 005
Revises: 004
Create Date: 2026-03-27
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _sqlite_table_has_column(conn, table: str, column: str) -> bool:
    r = conn.execute(sa.text(f"PRAGMA table_info({table})"))
    return any(row[1] == column for row in r.fetchall())


def upgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "sqlite":
        with op.batch_alter_table("custom_sounds") as batch_op:
            if not _sqlite_table_has_column(conn, "custom_sounds", "match_threshold"):
                batch_op.add_column(sa.Column("match_threshold", sa.Float(), nullable=True))
        with op.batch_alter_table("events") as batch_op:
            if not _sqlite_table_has_column(conn, "events", "custom_threshold_used"):
                batch_op.add_column(sa.Column("custom_threshold_used", sa.Float(), nullable=True))
            if not _sqlite_table_has_column(conn, "events", "custom_rms"):
                batch_op.add_column(sa.Column("custom_rms", sa.Float(), nullable=True))
            if not _sqlite_table_has_column(conn, "events", "custom_pick_reason"):
                batch_op.add_column(sa.Column("custom_pick_reason", sa.String(length=64), nullable=True))
    else:
        op.add_column("custom_sounds", sa.Column("match_threshold", sa.Float(), nullable=True))
        op.add_column("events", sa.Column("custom_threshold_used", sa.Float(), nullable=True))
        op.add_column("events", sa.Column("custom_rms", sa.Float(), nullable=True))
        op.add_column("events", sa.Column("custom_pick_reason", sa.String(length=64), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "sqlite":
        with op.batch_alter_table("events") as batch_op:
            if _sqlite_table_has_column(conn, "events", "custom_pick_reason"):
                batch_op.drop_column("custom_pick_reason")
            if _sqlite_table_has_column(conn, "events", "custom_rms"):
                batch_op.drop_column("custom_rms")
            if _sqlite_table_has_column(conn, "events", "custom_threshold_used"):
                batch_op.drop_column("custom_threshold_used")
        with op.batch_alter_table("custom_sounds") as batch_op:
            if _sqlite_table_has_column(conn, "custom_sounds", "match_threshold"):
                batch_op.drop_column("match_threshold")
    else:
        op.drop_column("events", "custom_pick_reason")
        op.drop_column("events", "custom_rms")
        op.drop_column("events", "custom_threshold_used")
        op.drop_column("custom_sounds", "match_threshold")
