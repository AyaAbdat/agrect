"""operation target

Revision ID: 0018
Revises: 0017
Create Date: 2026-11-23 22:45:00.000000

"""

import sqlalchemy as sa

from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("operation", sa.Column("target", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("operation", "target")
