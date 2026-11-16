"""catalog

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-11 20:29:39.214230

"""

import sqlalchemy as sa

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "crop",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.Enum("perennial", "annual", name="crop_kind"), nullable=False),
        sa.Column("sort", sa.Integer(), nullable=False),
        sa.Column("name_fr", sa.String(length=255), nullable=False),
        sa.Column("name_ar", sa.String(length=255), nullable=False),
        sa.Column("name_en", sa.String(length=255), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_crop")),
        sa.UniqueConstraint("code", name=op.f("uq_crop_code")),
    )
    op.create_table(
        "soil_texture_class",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("sort", sa.Integer(), nullable=False),
        sa.Column("name_fr", sa.String(length=255), nullable=False),
        sa.Column("name_ar", sa.String(length=255), nullable=False),
        sa.Column("name_en", sa.String(length=255), nullable=False),
        sa.Column("theta_fc_min", sa.Numeric(precision=5, scale=3), nullable=True),
        sa.Column("theta_fc_max", sa.Numeric(precision=5, scale=3), nullable=True),
        sa.Column("theta_wp_min", sa.Numeric(precision=5, scale=3), nullable=True),
        sa.Column("theta_wp_max", sa.Numeric(precision=5, scale=3), nullable=True),
        sa.Column("theta_fc", sa.Numeric(precision=5, scale=3), nullable=True),
        sa.Column("theta_wp", sa.Numeric(precision=5, scale=3), nullable=True),
        sa.Column("citation", sa.Text(), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_soil_texture_class")),
        sa.UniqueConstraint("code", name=op.f("uq_soil_texture_class_code")),
    )
    op.create_table(
        "training_system",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("crop_id", sa.UUID(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("sort", sa.Integer(), nullable=False),
        sa.Column("name_fr", sa.String(length=255), nullable=False),
        sa.Column("name_ar", sa.String(length=255), nullable=False),
        sa.Column("name_en", sa.String(length=255), nullable=False),
        sa.Column("description_fr", sa.Text(), nullable=False),
        sa.Column("description_ar", sa.Text(), nullable=False),
        sa.Column("description_en", sa.Text(), nullable=False),
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
            ["crop_id"],
            ["crop.id"],
            name=op.f("fk_training_system_crop_id_crop"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_training_system")),
        sa.UniqueConstraint("crop_id", "code", name=op.f("uq_training_system_crop_id")),
    )
    op.create_table(
        "variety",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("crop_id", sa.UUID(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("sort", sa.Integer(), nullable=False),
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
            ["crop_id"],
            ["crop.id"],
            name=op.f("fk_variety_crop_id_crop"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_variety")),
        sa.UniqueConstraint("crop_id", "code", name=op.f("uq_variety_crop_id")),
    )


def downgrade() -> None:
    op.drop_table("variety")
    op.drop_table("training_system")
    op.drop_table("soil_texture_class")
    op.drop_table("crop")
    sa.Enum("perennial", "annual", name="crop_kind").drop(op.get_bind(), checkfirst=False)
