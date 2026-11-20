"""phenology seasons

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-20 17:40:00.000000

"""

import sqlalchemy as sa

from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "block_season",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("farm_id", sa.UUID(), nullable=False),
        sa.Column("block_id", sa.UUID(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("start_stage_def_id", sa.UUID(), nullable=True),
        sa.Column("start_observed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "status",
            sa.Enum("open", "closed", name="season_status"),
            server_default=sa.text("'open'"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["block_id"],
            ["block.id"],
            name=op.f("fk_block_season_block_id_block"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["farm_id"],
            ["farm.id"],
            name=op.f("fk_block_season_farm_id_farm"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["start_stage_def_id"],
            ["stage_def.id"],
            name=op.f("fk_block_season_start_stage_def_id_stage_def"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_block_season")),
        sa.UniqueConstraint("block_id", "year", name=op.f("uq_block_season_block_id")),
    )
    op.create_index(op.f("ix_block_season_farm_id"), "block_season", ["farm_id"], unique=False)
    op.create_table(
        "stage_observation",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("farm_id", sa.UUID(), nullable=False),
        sa.Column("block_season_id", sa.UUID(), nullable=False),
        sa.Column("stage_def_id", sa.UUID(), nullable=False),
        sa.Column("observed_on", sa.Date(), nullable=False),
        sa.Column("share_pct", sa.Numeric(), nullable=True),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["block_season_id"],
            ["block_season.id"],
            name=op.f("fk_stage_observation_block_season_id_block_season"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["farm_id"],
            ["farm.id"],
            name=op.f("fk_stage_observation_farm_id_farm"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["stage_def_id"],
            ["stage_def.id"],
            name=op.f("fk_stage_observation_stage_def_id_stage_def"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app_user.id"],
            name=op.f("fk_stage_observation_user_id_app_user"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stage_observation")),
        sa.UniqueConstraint(
            "block_season_id",
            "stage_def_id",
            name=op.f("uq_stage_observation_block_season_id"),
        ),
    )
    op.create_index(
        op.f("ix_stage_observation_farm_id"),
        "stage_observation",
        ["farm_id"],
        unique=False,
    )
    op.create_table(
        "stage_prediction",
        sa.Column("block_season_id", sa.UUID(), nullable=False),
        sa.Column("stage_def_id", sa.UUID(), nullable=False),
        sa.Column("farm_id", sa.UUID(), nullable=False),
        sa.Column(
            "label",
            sa.Enum(
                "observed",
                "predicted",
                "not_enough_data",
                "beyond_data",
                name="prediction_label",
            ),
            nullable=False,
        ),
        sa.Column("predicted_on", sa.Date(), nullable=True),
        sa.Column("earliest", sa.Date(), nullable=True),
        sa.Column("latest", sa.Date(), nullable=True),
        sa.Column("dd_needed", sa.Numeric(), nullable=True),
        sa.Column("dd_counted", sa.Numeric(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("inputs_hash", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(
            ["block_season_id"],
            ["block_season.id"],
            name=op.f("fk_stage_prediction_block_season_id_block_season"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["farm_id"],
            ["farm.id"],
            name=op.f("fk_stage_prediction_farm_id_farm"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["stage_def_id"],
            ["stage_def.id"],
            name=op.f("fk_stage_prediction_stage_def_id_stage_def"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "block_season_id",
            "stage_def_id",
            name=op.f("pk_stage_prediction"),
        ),
    )
    op.create_index(
        op.f("ix_stage_prediction_farm_id"),
        "stage_prediction",
        ["farm_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_stage_prediction_farm_id"), table_name="stage_prediction")
    op.drop_table("stage_prediction")
    op.drop_index(op.f("ix_stage_observation_farm_id"), table_name="stage_observation")
    op.drop_table("stage_observation")
    op.drop_index(op.f("ix_block_season_farm_id"), table_name="block_season")
    op.drop_table("block_season")
    sa.Enum(
        "observed",
        "predicted",
        "not_enough_data",
        "beyond_data",
        name="prediction_label",
    ).drop(op.get_bind(), checkfirst=False)
    sa.Enum("open", "closed", name="season_status").drop(op.get_bind(), checkfirst=False)
