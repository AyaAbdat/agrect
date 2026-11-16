"""weather

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-15 22:22:33.057910

"""

import sqlalchemy as sa

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "farm_thresholds",
        sa.Column("farm_id", sa.UUID(), nullable=False),
        sa.Column("frost_c", sa.Numeric(), nullable=True),
        sa.Column("heat_c", sa.Numeric(), nullable=True),
        sa.Column("vpd_limit_kpa", sa.Numeric(), nullable=True),
        sa.Column("chill_season_start", sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(
            ["farm_id"],
            ["farm.id"],
            name=op.f("fk_farm_thresholds_farm_id_farm"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("farm_id", name=op.f("pk_farm_thresholds")),
    )
    op.create_table(
        "gdd_setting",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("farm_id", sa.UUID(), nullable=False),
        sa.Column("crop_id", sa.UUID(), nullable=False),
        sa.Column("base_c", sa.Numeric(), nullable=False),
        sa.Column("upper_c", sa.Numeric(), nullable=True),
        sa.Column("method", sa.Enum("average", "single_sine", name="gdd_method"), nullable=False),
        sa.ForeignKeyConstraint(
            ["crop_id"],
            ["crop.id"],
            name=op.f("fk_gdd_setting_crop_id_crop"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["farm_id"],
            ["farm.id"],
            name=op.f("fk_gdd_setting_farm_id_farm"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_gdd_setting")),
        sa.UniqueConstraint("farm_id", "crop_id", name=op.f("uq_gdd_setting_farm_id")),
    )
    op.create_table(
        "weather_daily",
        sa.Column("farm_id", sa.UUID(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("tmin_c", sa.Numeric(), nullable=True),
        sa.Column("tmax_c", sa.Numeric(), nullable=True),
        sa.Column("tmean_c", sa.Numeric(), nullable=True),
        sa.Column("rh_min", sa.Numeric(), nullable=True),
        sa.Column("rh_max", sa.Numeric(), nullable=True),
        sa.Column("rain_mm", sa.Numeric(), nullable=True),
        sa.Column("et0_mm", sa.Numeric(), nullable=True),
        sa.Column("vpd_max_kpa", sa.Numeric(), nullable=True),
        sa.Column("frost_h", sa.Integer(), nullable=True),
        sa.Column("heat_h", sa.Integer(), nullable=True),
        sa.Column("chill_h", sa.Integer(), nullable=True),
        sa.Column("hours_count", sa.Integer(), nullable=False),
        sa.Column("is_forecast", sa.Boolean(), nullable=False),
        sa.Column(
            "source",
            sa.String(length=32),
            server_default=sa.text("'estimated'"),
            nullable=False,
        ),
        sa.Column("inputs_hash", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(
            ["farm_id"],
            ["farm.id"],
            name=op.f("fk_weather_daily_farm_id_farm"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("farm_id", "date", name=op.f("pk_weather_daily")),
    )
    op.create_table(
        "weather_hourly",
        sa.Column("farm_id", sa.UUID(), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("temp_c", sa.Numeric(), nullable=True),
        sa.Column("rh_pct", sa.Numeric(), nullable=True),
        sa.Column("rain_mm", sa.Numeric(), nullable=True),
        sa.Column("rain_prob_pct", sa.Numeric(), nullable=True),
        sa.Column("wind_ms", sa.Numeric(), nullable=True),
        sa.Column("gust_ms", sa.Numeric(), nullable=True),
        sa.Column("wind_dir_deg", sa.Numeric(), nullable=True),
        sa.Column("rad_wm2", sa.Numeric(), nullable=True),
        sa.Column("et0_mm", sa.Numeric(), nullable=True),
        sa.Column("dewpoint_c", sa.Numeric(), nullable=True),
        sa.Column("vpd_kpa", sa.Numeric(), nullable=True),
        sa.Column("is_forecast", sa.Boolean(), nullable=False),
        sa.Column(
            "source",
            sa.String(length=32),
            server_default=sa.text("'estimated'"),
            nullable=False,
        ),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["farm_id"],
            ["farm.id"],
            name=op.f("fk_weather_hourly_farm_id_farm"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("farm_id", "ts", name=op.f("pk_weather_hourly")),
    )


def downgrade() -> None:
    op.drop_table("weather_hourly")
    op.drop_table("weather_daily")
    op.drop_table("gdd_setting")
    op.drop_table("farm_thresholds")
    sa.Enum("average", "single_sine", name="gdd_method").drop(op.get_bind(), checkfirst=False)
