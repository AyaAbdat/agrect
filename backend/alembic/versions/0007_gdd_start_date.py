"""gdd start date

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-15 22:46:58.905614

"""

import sqlalchemy as sa

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("gdd_setting", sa.Column("start_date", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("gdd_setting", "start_date")
