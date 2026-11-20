"""gdd setting block

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-20 19:10:00.000000

"""

import sqlalchemy as sa

from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "gdd_setting_block",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("farm_id", sa.UUID(), nullable=False),
        sa.Column("block_id", sa.UUID(), nullable=False),
        sa.Column("base_c", sa.Numeric(), nullable=False),
        sa.Column("upper_c", sa.Numeric(), nullable=True),
        sa.Column(
            "method",
            sa.Enum("average", "single_sine", name="gdd_method", create_type=False),
            nullable=False,
        ),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.ForeignKeyConstraint(
            ["block_id"],
            ["block.id"],
            name=op.f("fk_gdd_setting_block_block_id_block"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["farm_id"],
            ["farm.id"],
            name=op.f("fk_gdd_setting_block_farm_id_farm"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_gdd_setting_block")),
        sa.UniqueConstraint("block_id", name=op.f("uq_gdd_setting_block_block_id")),
    )
    op.create_index(
        op.f("ix_gdd_setting_block_farm_id"),
        "gdd_setting_block",
        ["farm_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_gdd_setting_block_farm_id"), table_name="gdd_setting_block")
    op.drop_table("gdd_setting_block")
