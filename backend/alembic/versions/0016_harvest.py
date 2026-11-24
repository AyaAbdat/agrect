"""harvest

Revision ID: 0016
Revises: 0015
Create Date: 2026-11-23 21:30:00.000000

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "harvest_entry",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("farm_id", sa.UUID(), nullable=False),
        sa.Column("block_id", sa.UUID(), nullable=False),
        sa.Column("valve_id", sa.UUID(), nullable=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("pass_no", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("quantity", sa.Numeric(), nullable=False),
        sa.Column(
            "unit",
            sa.Enum("kg", "t", "crate", "bin", name="harvest_unit"),
            nullable=False,
        ),
        sa.Column("unit_weight_kg", sa.Numeric(), nullable=True),
        sa.Column(
            "basis",
            sa.Enum("block", "valve", "rows", "trees", name="harvest_basis"),
            nullable=False,
        ),
        sa.Column("basis_count", sa.Numeric(), nullable=True),
        sa.Column("kg", sa.Numeric(), nullable=False),
        sa.Column("kg_ha", sa.Numeric(), nullable=False),
        sa.Column("area_ha", sa.Numeric(), nullable=False),
        sa.Column("inputs_hash", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["block_id"],
            ["block.id"],
            name=op.f("fk_harvest_entry_block_id_block"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["farm_id"],
            ["farm.id"],
            name=op.f("fk_harvest_entry_farm_id_farm"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app_user.id"],
            name=op.f("fk_harvest_entry_user_id_app_user"),
        ),
        sa.ForeignKeyConstraint(
            ["valve_id"],
            ["valve.id"],
            name=op.f("fk_harvest_entry_valve_id_valve"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_harvest_entry")),
    )
    op.create_index(op.f("ix_harvest_entry_farm_id"), "harvest_entry", ["farm_id"], unique=False)
    op.create_index(op.f("ix_harvest_entry_block_id"), "harvest_entry", ["block_id"], unique=False)
    op.create_table(
        "harvest_quality",
        sa.Column("harvest_entry_id", sa.UUID(), nullable=False),
        sa.Column("brix", sa.Numeric(), nullable=True),
        sa.Column("size_grade", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("waste_pct", sa.Numeric(), nullable=True),
        sa.Column("moisture_pct", sa.Numeric(), nullable=True),
        sa.Column("protein_pct", sa.Numeric(), nullable=True),
        sa.Column("test_weight_kg_hl", sa.Numeric(), nullable=True),
        sa.ForeignKeyConstraint(
            ["harvest_entry_id"],
            ["harvest_entry.id"],
            name=op.f("fk_harvest_quality_harvest_entry_id_harvest_entry"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("harvest_entry_id", name=op.f("pk_harvest_quality")),
    )


def downgrade() -> None:
    op.drop_table("harvest_quality")
    op.drop_index(op.f("ix_harvest_entry_block_id"), table_name="harvest_entry")
    op.drop_index(op.f("ix_harvest_entry_farm_id"), table_name="harvest_entry")
    op.drop_table("harvest_entry")
    sa.Enum(name="harvest_basis").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="harvest_unit").drop(op.get_bind(), checkfirst=True)
