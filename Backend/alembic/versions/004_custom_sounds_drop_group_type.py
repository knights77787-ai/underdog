"""custom_sounds.group_type 컬럼 제거

Revision ID: 004
Revises: 003
Create Date: custom_sounds group_type 컬럼 삭제 (event_type만 사용)

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _sqlite_table_has_column(conn, table: str, column: str) -> bool:
    r = conn.execute(sa.text(f"PRAGMA table_info({table})"))
    return any(row[1] == column for row in r.fetchall())


def upgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "sqlite":
        if _sqlite_table_has_column(conn, "custom_sounds", "group_type"):
            with op.batch_alter_table("custom_sounds") as batch_op:
                batch_op.drop_column("group_type")
    else:
        op.drop_column("custom_sounds", "group_type")


def downgrade() -> None:
    op.add_column(
        "custom_sounds",
        sa.Column("group_type", sa.String(32), nullable=True),
    )
