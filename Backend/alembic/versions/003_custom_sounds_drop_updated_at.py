"""custom_sounds.updated_at 컬럼 제거

Revision ID: 003
Revises: 002
Create Date: custom_sounds updated_at 제거

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _sqlite_table_has_column(conn, table: str, column: str) -> bool:
    r = conn.execute(sa.text(f"PRAGMA table_info({table})"))
    return any(row[1] == column for row in r.fetchall())


def upgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "sqlite":
        if _sqlite_table_has_column(conn, "custom_sounds", "updated_at"):
            with op.batch_alter_table("custom_sounds") as batch_op:
                batch_op.drop_column("updated_at")
    else:
        op.drop_column("custom_sounds", "updated_at")


def downgrade() -> None:
    op.add_column(
        "custom_sounds",
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
