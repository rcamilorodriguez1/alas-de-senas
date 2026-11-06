"""autorizacion de datos

Autorización de tratamiento de datos (Ley 1581, D-037): fecha y versión de la política.
Las cuentas creadas antes quedan en NULL: aceptaron la casilla, pero no se registró cuándo (no
se inventa una fecha).

Revision ID: 8483232b2587
Revises: 3c8e1f5a9d27
Create Date: 2026-11-06 13:02:23.341520
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "8483232b2587"
down_revision: str | None = "3c8e1f5a9d27"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users", sa.Column("data_policy_accepted_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("users", sa.Column("data_policy_version", sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "data_policy_version")
    op.drop_column("users", "data_policy_accepted_at")
