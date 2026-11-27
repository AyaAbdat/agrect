"""price version

Revision ID: 0020
Revises: 0019
Create Date: 2026-11-24 15:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "price",
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("price", "version")
