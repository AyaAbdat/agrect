"""registry planting layout valves

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-14 15:01:15.462207

"""

import sqlalchemy as sa

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "irrigation_layout",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("farm_id", sa.UUID(), nullable=False),
        sa.Column("block_id", sa.UUID(), nullable=False),
        sa.Column(
            "system",
            sa.Enum(
                "drip",
                "subsurface_drip",
                "micro_sprinkler",
                "bubbler",
                "sprinkler",
                name="irrigation_system",
            ),
            nullable=False,
        ),
        sa.Column(
            "entry_mode",
            sa.Enum("layout", "per_tree", "typed_flow", name="flow_entry_mode"),
            nullable=False,
        ),
        sa.Column("laterals_per_row", sa.Integer(), nullable=True),
        sa.Column("emitter_spacing_m", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("emitter_flow_lph", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("emitters_per_tree", sa.Integer(), nullable=True),
        sa.Column("flow_per_emitter_lph", sa.Numeric(precision=7, scale=2), nullable=True),
        sa.Column("typed_flow_m3h", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column(
            "typed_flow_basis",
            sa.Enum("block", "ha", "valve", name="typed_flow_basis"),
            nullable=True,
        ),
        sa.Column("flow_meter", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("q_ha_m3h", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("q_block_m3h", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("rate_mm_h", sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column("inputs_hash", sa.String(length=64), nullable=True),
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
            name=op.f("fk_irrigation_layout_block_id_block"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["farm_id"],
            ["farm.id"],
            name=op.f("fk_irrigation_layout_farm_id_farm"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_irrigation_layout")),
        sa.UniqueConstraint("block_id", name=op.f("uq_irrigation_layout_block_id")),
    )
    op.create_index(
        op.f("ix_irrigation_layout_farm_id"), "irrigation_layout", ["farm_id"], unique=False
    )
    op.create_table(
        "planting",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("farm_id", sa.UUID(), nullable=False),
        sa.Column("block_id", sa.UUID(), nullable=False),
        sa.Column("variety_id", sa.UUID(), nullable=True),
        sa.Column("variety_text", sa.Text(), nullable=True),
        sa.Column("rootstock", sa.Text(), nullable=True),
        sa.Column("planting_year", sa.Integer(), nullable=True),
        sa.Column(
            "density_input",
            sa.Enum("spacing", "density", "count", name="density_input"),
            nullable=True,
        ),
        sa.Column("row_spacing_m", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("tree_spacing_m", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("trees_per_ha", sa.Integer(), nullable=True),
        sa.Column("trees_count", sa.Integer(), nullable=True),
        sa.Column("area_ha", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("sort", sa.Integer(), nullable=False),
        sa.Column("inputs_hash", sa.String(length=64), nullable=True),
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
            ["block_id"], ["block.id"], name=op.f("fk_planting_block_id_block"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["farm_id"], ["farm.id"], name=op.f("fk_planting_farm_id_farm"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["variety_id"], ["variety.id"], name=op.f("fk_planting_variety_id_variety")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_planting")),
    )
    op.create_index(op.f("ix_planting_block_id"), "planting", ["block_id"], unique=False)
    op.create_index(op.f("ix_planting_farm_id"), "planting", ["farm_id"], unique=False)
    op.create_table(
        "valve",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("farm_id", sa.UUID(), nullable=False),
        sa.Column("block_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("sort", sa.Integer(), nullable=False),
        sa.Column("row_from", sa.Integer(), nullable=False),
        sa.Column("row_to", sa.Integer(), nullable=False),
        sa.Column("typed_q_m3h", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("area_ha", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("q_m3h", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("inputs_hash", sa.String(length=64), nullable=True),
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
            ["block_id"], ["block.id"], name=op.f("fk_valve_block_id_block"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["farm_id"], ["farm.id"], name=op.f("fk_valve_farm_id_farm"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_valve")),
    )
    op.create_index(op.f("ix_valve_block_id"), "valve", ["block_id"], unique=False)
    op.create_index(op.f("ix_valve_farm_id"), "valve", ["farm_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_valve_farm_id"), table_name="valve")
    op.drop_index(op.f("ix_valve_block_id"), table_name="valve")
    op.drop_table("valve")
    op.drop_index(op.f("ix_planting_farm_id"), table_name="planting")
    op.drop_index(op.f("ix_planting_block_id"), table_name="planting")
    op.drop_table("planting")
    op.drop_index(op.f("ix_irrigation_layout_farm_id"), table_name="irrigation_layout")
    op.drop_table("irrigation_layout")
    sa.Enum("spacing", "density", "count", name="density_input").drop(
        op.get_bind(), checkfirst=False
    )
    sa.Enum(
        "drip",
        "subsurface_drip",
        "micro_sprinkler",
        "bubbler",
        "sprinkler",
        name="irrigation_system",
    ).drop(op.get_bind(), checkfirst=False)
    sa.Enum("layout", "per_tree", "typed_flow", name="flow_entry_mode").drop(
        op.get_bind(), checkfirst=False
    )
    sa.Enum("block", "ha", "valve", name="typed_flow_basis").drop(op.get_bind(), checkfirst=False)
