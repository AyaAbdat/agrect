"""chill portions

Revision ID: 0015
Revises: 0014
Create Date: 2026-11-23 21:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "weather_daily",
        sa.Column("chill_portions", sa.Numeric(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("weather_daily", "chill_portions")
