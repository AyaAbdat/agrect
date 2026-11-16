"""auth and farm

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-06 20:51:40.173986

"""

import sqlalchemy as sa
from geoalchemy2 import Geometry

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "app_user",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=512), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_app_user")),
        sa.UniqueConstraint("email", name=op.f("uq_app_user_email")),
    )
    op.create_geospatial_table(
        "farm",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("owner_user_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "location",
            Geometry(
                geometry_type="POINT",
                srid=4326,
                dimension=2,
                spatial_index=False,
                from_text="ST_GeomFromEWKT",
                name="geometry",
            ),
            nullable=True,
        ),
        sa.Column(
            "timezone",
            sa.String(length=64),
            server_default=sa.text("'Africa/Algiers'"),
            nullable=False,
        ),
        sa.Column(
            "weather_source",
            sa.Enum("station", "service", name="weather_source"),
            server_default=sa.text("'service'"),
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
            ["owner_user_id"],
            ["app_user.id"],
            name=op.f("fk_farm_owner_user_id_app_user"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_farm")),
    )
    op.create_geospatial_index(
        "idx_farm_location",
        "farm",
        ["location"],
        unique=False,
        postgresql_using="gist",
        postgresql_ops={},
    )
    op.create_index(op.f("ix_farm_owner_user_id"), "farm", ["owner_user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_farm_owner_user_id"), table_name="farm")
    op.drop_geospatial_index(
        "idx_farm_location",
        table_name="farm",
        postgresql_using="gist",
        column_name="location",
    )
    op.drop_geospatial_table("farm")
    op.drop_table("app_user")
    sa.Enum("station", "service", name="weather_source").drop(op.get_bind(), checkfirst=False)
