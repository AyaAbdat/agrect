"""soil and irrigation settings

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-16 21:43:17.989742

"""

import sqlalchemy as sa

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "irrigation_settings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("farm_id", sa.UUID(), nullable=False),
        sa.Column("block_id", sa.UUID(), nullable=False),
        sa.Column("efficiency", sa.Numeric(precision=4, scale=3), nullable=True),
        sa.Column("kc", sa.Numeric(precision=4, scale=2), nullable=True),
        sa.Column(
            "kc_source",
            sa.Enum("suggested", "entered", name="kc_source"),
            nullable=True,
        ),
        sa.Column("stage_override_id", sa.UUID(), nullable=True),
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
            name=op.f("fk_irrigation_settings_block_id_block"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["farm_id"],
            ["farm.id"],
            name=op.f("fk_irrigation_settings_farm_id_farm"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_irrigation_settings")),
        sa.UniqueConstraint("block_id", name=op.f("uq_irrigation_settings_block_id")),
    )
    op.create_index(
        op.f("ix_irrigation_settings_farm_id"),
        "irrigation_settings",
        ["farm_id"],
        unique=False,
    )
    op.create_table(
        "soil_profile",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("farm_id", sa.UUID(), nullable=False),
        sa.Column("block_id", sa.UUID(), nullable=False),
        sa.Column(
            "texture_mode",
            sa.Enum("class", "percent", name="texture_mode"),
            nullable=False,
        ),
        sa.Column("texture_class_id", sa.UUID(), nullable=True),
        sa.Column("sand_pct", sa.Numeric(), nullable=True),
        sa.Column("silt_pct", sa.Numeric(), nullable=True),
        sa.Column("clay_pct", sa.Numeric(), nullable=True),
        sa.Column("theta_fc", sa.Numeric(precision=5, scale=3), nullable=True),
        sa.Column("theta_wp", sa.Numeric(precision=5, scale=3), nullable=True),
        sa.Column("root_depth_m", sa.Numeric(precision=4, scale=2), nullable=True),
        sa.Column("dry_down_pct", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("full_on", sa.Date(), nullable=True),
        sa.Column("organic_matter_pct", sa.Numeric(), nullable=True),
        sa.Column(
            "compaction",
            sa.Enum("loose", "normal", "compacted", name="compaction"),
            nullable=True,
        ),
        sa.Column("infiltration_mm_h", sa.Numeric(), nullable=True),
        sa.Column(
            "infiltration_source",
            sa.Enum("texture", "ring_test", name="infiltration_source"),
            nullable=True,
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
            ["block_id"],
            ["block.id"],
            name=op.f("fk_soil_profile_block_id_block"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["farm_id"],
            ["farm.id"],
            name=op.f("fk_soil_profile_farm_id_farm"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["texture_class_id"],
            ["soil_texture_class.id"],
            name=op.f("fk_soil_profile_texture_class_id_soil_texture_class"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_soil_profile")),
        sa.UniqueConstraint("block_id", name=op.f("uq_soil_profile_block_id")),
    )
    op.create_index(op.f("ix_soil_profile_farm_id"), "soil_profile", ["farm_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_soil_profile_farm_id"), table_name="soil_profile")
    op.drop_table("soil_profile")
    op.drop_index(op.f("ix_irrigation_settings_farm_id"), table_name="irrigation_settings")
    op.drop_table("irrigation_settings")
    sa.Enum("class", "percent", name="texture_mode").drop(op.get_bind(), checkfirst=False)
    sa.Enum("loose", "normal", "compacted", name="compaction").drop(op.get_bind(), checkfirst=False)
    sa.Enum("texture", "ring_test", name="infiltration_source").drop(
        op.get_bind(), checkfirst=False
    )
    sa.Enum("suggested", "entered", name="kc_source").drop(op.get_bind(), checkfirst=False)
