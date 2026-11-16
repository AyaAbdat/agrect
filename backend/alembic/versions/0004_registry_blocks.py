"""registry blocks

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-11 21:33:38.170316

"""

import sqlalchemy as sa
from geoalchemy2 import Geometry
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_geospatial_table(
        "block",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("farm_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            sa.Enum("draft", "complete", "archived", name="block_status"),
            server_default=sa.text("'draft'"),
            nullable=False,
        ),
        sa.Column(
            "outline",
            Geometry(
                geometry_type="POLYGON",
                srid=4326,
                dimension=2,
                spatial_index=False,
                from_text="ST_GeomFromEWKT",
                name="geometry",
            ),
            nullable=True,
        ),
        sa.Column(
            "row_line",
            Geometry(
                geometry_type="LINESTRING",
                srid=4326,
                dimension=2,
                spatial_index=False,
                from_text="ST_GeomFromEWKT",
                name="geometry",
            ),
            nullable=True,
        ),
        sa.Column("gross_area_ha", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("row_bearing_deg", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("net_area_ha", sa.Numeric(precision=12, scale=4), nullable=True),
        sa.Column("rows_total", sa.Integer(), nullable=True),
        sa.Column("crop_id", sa.UUID(), nullable=True),
        sa.Column("training_system_id", sa.UUID(), nullable=True),
        sa.Column("training_other", sa.Text(), nullable=True),
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
            ["crop_id"],
            ["crop.id"],
            name=op.f("fk_block_crop_id_crop"),
        ),
        sa.ForeignKeyConstraint(
            ["farm_id"],
            ["farm.id"],
            name=op.f("fk_block_farm_id_farm"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["training_system_id"],
            ["training_system.id"],
            name=op.f("fk_block_training_system_id_training_system"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_block")),
        sa.UniqueConstraint("farm_id", "name", name=op.f("uq_block_farm_id")),
    )
    op.create_geospatial_index(
        "idx_block_outline",
        "block",
        ["outline"],
        unique=False,
        postgresql_using="gist",
        postgresql_ops={},
    )
    op.create_geospatial_index(
        "idx_block_row_line",
        "block",
        ["row_line"],
        unique=False,
        postgresql_using="gist",
        postgresql_ops={},
    )
    op.create_index(op.f("ix_block_farm_id"), "block", ["farm_id"], unique=False)
    op.create_table(
        "record_version",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("farm_id", sa.UUID(), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("changed_fields", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column(
            "changed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["farm_id"],
            ["farm.id"],
            name=op.f("fk_record_version_farm_id_farm"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app_user.id"],
            name=op.f("fk_record_version_user_id_app_user"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_record_version")),
    )
    op.create_index(
        op.f("ix_record_version_entity_id"),
        "record_version",
        ["entity_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_record_version_farm_id"),
        "record_version",
        ["farm_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_record_version_farm_id"), table_name="record_version")
    op.drop_index(op.f("ix_record_version_entity_id"), table_name="record_version")
    op.drop_table("record_version")
    op.drop_index(op.f("ix_block_farm_id"), table_name="block")
    op.drop_geospatial_index(
        "idx_block_row_line",
        table_name="block",
        postgresql_using="gist",
        column_name="row_line",
    )
    op.drop_geospatial_index(
        "idx_block_outline",
        table_name="block",
        postgresql_using="gist",
        column_name="outline",
    )
    op.drop_geospatial_table("block")
    sa.Enum("draft", "complete", "archived", name="block_status").drop(
        op.get_bind(),
        checkfirst=False,
    )
