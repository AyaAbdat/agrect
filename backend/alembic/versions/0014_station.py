"""station

Revision ID: 0014
Revises: 0013
Create Date: 2026-11-21 19:40:00.000000

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "station",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("farm_id", sa.UUID(), nullable=False),
        sa.Column(
            "name",
            sa.String(length=255),
            server_default=sa.text("'Station'"),
            nullable=False,
        ),
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
            ["farm_id"],
            ["farm.id"],
            name=op.f("fk_station_farm_id_farm"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_station")),
        sa.UniqueConstraint("farm_id", name=op.f("uq_station_farm_id")),
    )
    op.create_table(
        "water_source",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("farm_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "kind",
            sa.Enum("borehole", "basin", "network", name="water_source_kind"),
            nullable=False,
        ),
        sa.Column("ec_ds_m", sa.Numeric(), nullable=True),
        sa.Column("basin_volume_m3", sa.Numeric(), nullable=True),
        sa.ForeignKeyConstraint(
            ["farm_id"],
            ["farm.id"],
            name=op.f("fk_water_source_farm_id_farm"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_water_source")),
    )
    op.create_index(
        op.f("ix_water_source_farm_id"),
        "water_source",
        ["farm_id"],
        unique=False,
    )
    op.create_table(
        "pump",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("farm_id", sa.UUID(), nullable=False),
        sa.Column("station_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("flow_m3h", sa.Numeric(), nullable=False),
        sa.Column(
            "serves_all_blocks",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column("pressure_bar", sa.Numeric(), nullable=True),
        sa.Column("water_source_id", sa.UUID(), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.CheckConstraint("flow_m3h > 0", name=op.f("ck_pump_flow_positive")),
        sa.ForeignKeyConstraint(
            ["farm_id"],
            ["farm.id"],
            name=op.f("fk_pump_farm_id_farm"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["station_id"],
            ["station.id"],
            name=op.f("fk_pump_station_id_station"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["water_source_id"],
            ["water_source.id"],
            name=op.f("fk_pump_water_source_id_water_source"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pump")),
        sa.UniqueConstraint("station_id", "name", name=op.f("uq_pump_station_id")),
    )
    op.create_index(op.f("ix_pump_farm_id"), "pump", ["farm_id"], unique=False)
    op.create_index(op.f("ix_pump_water_source_id"), "pump", ["water_source_id"], unique=False)
    op.create_table(
        "pump_block",
        sa.Column("pump_id", sa.UUID(), nullable=False),
        sa.Column("block_id", sa.UUID(), nullable=False),
        sa.Column("farm_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["block_id"],
            ["block.id"],
            name=op.f("fk_pump_block_block_id_block"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["farm_id"],
            ["farm.id"],
            name=op.f("fk_pump_block_farm_id_farm"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["pump_id"],
            ["pump.id"],
            name=op.f("fk_pump_block_pump_id_pump"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("pump_id", "block_id", name=op.f("pk_pump_block")),
    )
    op.create_index(op.f("ix_pump_block_farm_id"), "pump_block", ["farm_id"], unique=False)
    op.create_table(
        "pump_window",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("farm_id", sa.UUID(), nullable=False),
        sa.Column("pump_id", sa.UUID(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.ForeignKeyConstraint(
            ["farm_id"],
            ["farm.id"],
            name=op.f("fk_pump_window_farm_id_farm"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["pump_id"],
            ["pump.id"],
            name=op.f("fk_pump_window_pump_id_pump"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pump_window")),
    )
    op.create_index(op.f("ix_pump_window_farm_id"), "pump_window", ["farm_id"], unique=False)
    op.create_index(op.f("ix_pump_window_pump_id"), "pump_window", ["pump_id"], unique=False)
    op.create_table(
        "capacity_decision",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("farm_id", sa.UUID(), nullable=False),
        sa.Column(
            "choice",
            sa.Enum("priority", "share", "more_shifts", name="capacity_choice"),
            nullable=False,
        ),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("block_ids", postgresql.ARRAY(sa.UUID()), nullable=True),
        sa.Column(
            "mode",
            sa.Enum("today", "peak_week", name="capacity_mode"),
            nullable=False,
        ),
        sa.Column("snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["farm_id"],
            ["farm.id"],
            name=op.f("fk_capacity_decision_farm_id_farm"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app_user.id"],
            name=op.f("fk_capacity_decision_user_id_app_user"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_capacity_decision")),
    )
    op.create_index(
        op.f("ix_capacity_decision_farm_id"),
        "capacity_decision",
        ["farm_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_capacity_decision_farm_id"), table_name="capacity_decision")
    op.drop_table("capacity_decision")
    op.drop_index(op.f("ix_pump_window_pump_id"), table_name="pump_window")
    op.drop_index(op.f("ix_pump_window_farm_id"), table_name="pump_window")
    op.drop_table("pump_window")
    op.drop_index(op.f("ix_pump_block_farm_id"), table_name="pump_block")
    op.drop_table("pump_block")
    op.drop_index(op.f("ix_pump_water_source_id"), table_name="pump")
    op.drop_index(op.f("ix_pump_farm_id"), table_name="pump")
    op.drop_table("pump")
    op.drop_index(op.f("ix_water_source_farm_id"), table_name="water_source")
    op.drop_table("water_source")
    op.drop_table("station")
    sa.Enum("today", "peak_week", name="capacity_mode").drop(op.get_bind(), checkfirst=False)
    sa.Enum("priority", "share", "more_shifts", name="capacity_choice").drop(
        op.get_bind(), checkfirst=False
    )
    sa.Enum("borehole", "basin", "network", name="water_source_kind").drop(
        op.get_bind(), checkfirst=False
    )
