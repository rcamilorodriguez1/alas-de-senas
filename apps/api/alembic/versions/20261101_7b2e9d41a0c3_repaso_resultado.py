"""repaso: resultado guardado para el complete idempotente (D-014).

Revision ID: 7b2e9d41a0c3
Revises: f25914da6c54
Create Date: 2026-11-01 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "7b2e9d41a0c3"
down_revision: str | None = "f25914da6c54"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "review_sessions",
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("review_sessions", "result")
