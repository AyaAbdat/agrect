"""history daily

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-20 17:18:01.941894

"""

import sqlalchemy as sa

from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "history_daily",
        sa.Column("farm_id", sa.UUID(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("tmin_c", sa.Numeric(), nullable=True),
        sa.Column("tmax_c", sa.Numeric(), nullable=True),
        sa.Column("rain_mm", sa.Numeric(), nullable=True),
        sa.Column("et0_mm", sa.Numeric(), nullable=True),
        sa.Column(
            "source",
            sa.String(length=32),
            server_default=sa.text("'estimated'"),
            nullable=False,
        ),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["farm_id"],
            ["farm.id"],
            name=op.f("fk_history_daily_farm_id_farm"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("farm_id", "date", name=op.f("pk_history_daily")),
    )


def downgrade() -> None:
    op.drop_table("history_daily")
