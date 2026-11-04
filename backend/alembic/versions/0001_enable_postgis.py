"""enable postgis

Revision ID: 0001
Revises:
Create Date: 2026-11-04 21:53:11.059164

"""

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")


def downgrade() -> None:
    """The extension is kept on purpose."""
