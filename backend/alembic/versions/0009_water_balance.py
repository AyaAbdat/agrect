"""water balance

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-16 22:10:44.960539

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "irrigation_event",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("farm_id", sa.UUID(), nullable=False),
        sa.Column("block_id", sa.UUID(), nullable=False),
        sa.Column("valve_ids", postgresql.ARRAY(sa.UUID()), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_min", sa.Integer(), nullable=False),
        sa.Column("depth_mm", sa.Numeric(), nullable=False),
        sa.Column("volume_m3", sa.Numeric(), nullable=False),
        sa.Column("soil_mm", sa.Numeric(), nullable=False),
        sa.Column("runoff_mm", sa.Numeric(), nullable=False),
        sa.Column(
            "source",
            sa.Enum("calculated", "measured", name="irrigation_source"),
            nullable=False,
        ),
        sa.Column("entered_by", sa.UUID(), nullable=False),
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
        sa.CheckConstraint(
            "cardinality(valve_ids) > 0",
            name=op.f("ck_irrigation_event_valve_ids_not_empty"),
        ),
        sa.ForeignKeyConstraint(
            ["block_id"],
            ["block.id"],
            name=op.f("fk_irrigation_event_block_id_block"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["entered_by"],
            ["app_user.id"],
            name=op.f("fk_irrigation_event_entered_by_app_user"),
        ),
        sa.ForeignKeyConstraint(
            ["farm_id"],
            ["farm.id"],
            name=op.f("fk_irrigation_event_farm_id_farm"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_irrigation_event")),
    )
    op.create_index(
        op.f("ix_irrigation_event_block_id"),
        "irrigation_event",
        ["block_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_irrigation_event_farm_id"),
        "irrigation_event",
        ["farm_id"],
        unique=False,
    )
    op.create_table(
        "soil_check",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("farm_id", sa.UUID(), nullable=False),
        sa.Column("block_id", sa.UUID(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column(
            "depth_band",
            sa.Enum("0_30", "30_60", name="depth_band"),
            nullable=False,
        ),
        sa.Column(
            "feel",
            sa.Enum("dry", "slightly_moist", "moist", "wet", name="soil_feel"),
            nullable=False,
        ),
        sa.Column("reset_depletion_mm", sa.Numeric(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["block_id"],
            ["block.id"],
            name=op.f("fk_soil_check_block_id_block"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["farm_id"],
            ["farm.id"],
            name=op.f("fk_soil_check_farm_id_farm"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_soil_check")),
    )
    op.create_index(op.f("ix_soil_check_block_id"), "soil_check", ["block_id"], unique=False)
    op.create_index(op.f("ix_soil_check_farm_id"), "soil_check", ["farm_id"], unique=False)
    op.create_table(
        "water_balance_daily",
        sa.Column("block_id", sa.UUID(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("farm_id", sa.UUID(), nullable=False),
        sa.Column("et0_mm", sa.Numeric(), nullable=True),
        sa.Column("kc", sa.Numeric(), nullable=True),
        sa.Column("etc_mm", sa.Numeric(), nullable=True),
        sa.Column("rain_mm", sa.Numeric(), nullable=True),
        sa.Column("irrigation_soil_mm", sa.Numeric(), nullable=True),
        sa.Column("runoff_mm", sa.Numeric(), nullable=True),
        sa.Column("drainage_mm", sa.Numeric(), nullable=True),
        sa.Column("depletion_mm", sa.Numeric(), nullable=True),
        sa.Column("taw_mm", sa.Numeric(), nullable=True),
        sa.Column("raw_mm", sa.Numeric(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("ok", "irrigate_soon", "no_data", name="wb_status"),
            nullable=False,
        ),
        sa.Column("is_forecast", sa.Boolean(), nullable=False),
        sa.Column("inputs_hash", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(
            ["block_id"],
            ["block.id"],
            name=op.f("fk_water_balance_daily_block_id_block"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["farm_id"],
            ["farm.id"],
            name=op.f("fk_water_balance_daily_farm_id_farm"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("block_id", "date", name=op.f("pk_water_balance_daily")),
    )
    op.create_index(
        op.f("ix_water_balance_daily_farm_id"),
        "water_balance_daily",
        ["farm_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_water_balance_daily_farm_id"), table_name="water_balance_daily")
    op.drop_table("water_balance_daily")
    op.drop_index(op.f("ix_soil_check_farm_id"), table_name="soil_check")
    op.drop_index(op.f("ix_soil_check_block_id"), table_name="soil_check")
    op.drop_table("soil_check")
    op.drop_index(op.f("ix_irrigation_event_farm_id"), table_name="irrigation_event")
    op.drop_index(op.f("ix_irrigation_event_block_id"), table_name="irrigation_event")
    op.drop_table("irrigation_event")
    sa.Enum("calculated", "measured", name="irrigation_source").drop(
        op.get_bind(), checkfirst=False
    )
    sa.Enum("0_30", "30_60", name="depth_band").drop(op.get_bind(), checkfirst=False)
    sa.Enum("dry", "slightly_moist", "moist", "wet", name="soil_feel").drop(
        op.get_bind(), checkfirst=False
    )
    sa.Enum("ok", "irrigate_soon", "no_data", name="wb_status").drop(
        op.get_bind(), checkfirst=False
    )
