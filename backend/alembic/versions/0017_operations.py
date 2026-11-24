"""operations

Revision ID: 0017
Revises: 0016
Create Date: 2026-11-23 22:15:00.000000

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "product",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("farm_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "fertiliser",
                "crop_protection",
                "seed",
                "packaging",
                "other",
                name="product_kind",
            ),
            nullable=False,
        ),
        sa.Column(
            "unit",
            sa.Enum("kg", "g", "l", "ml", "unit", name="product_unit"),
            nullable=False,
        ),
        sa.Column("active_ingredient", sa.Text(), nullable=True),
        sa.Column("nutrient_n_pct", sa.Numeric(), nullable=True),
        sa.Column("nutrient_p2o5_pct", sa.Numeric(), nullable=True),
        sa.Column("nutrient_k2o_pct", sa.Numeric(), nullable=True),
        sa.Column("preharvest_interval_days", sa.Integer(), nullable=True),
        sa.Column("reentry_h", sa.Integer(), nullable=True),
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
            name=op.f("fk_product_farm_id_farm"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_product")),
        sa.UniqueConstraint("farm_id", "name", name="uq_product_farm_id_name"),
    )
    op.create_index(op.f("ix_product_farm_id"), "product", ["farm_id"], unique=False)

    op.create_table(
        "operation",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("farm_id", sa.UUID(), nullable=False),
        sa.Column("block_id", sa.UUID(), nullable=False),
        sa.Column(
            "valve_ids",
            postgresql.ARRAY(sa.UUID()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column(
            "type",
            sa.Enum(
                "fertigation",
                "foliar_application",
                "crop_protection_spray",
                "herbicide",
                "pruning",
                "shoot_cluster_thinning",
                "growth_regulator",
                "girdling",
                "leaf_removal",
                "cover_netting",
                "tillage",
                "sowing",
                "nitrogen_application",
                "other",
                name="operation_type",
            ),
            nullable=False,
        ),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_min", sa.Integer(), nullable=True),
        sa.Column("workers_count", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("area_ha", sa.Numeric(), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
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
            name=op.f("fk_operation_block_id_block"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["farm_id"],
            ["farm.id"],
            name=op.f("fk_operation_farm_id_farm"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app_user.id"],
            name=op.f("fk_operation_user_id_app_user"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_operation")),
    )
    op.create_index(op.f("ix_operation_farm_id"), "operation", ["farm_id"], unique=False)
    op.create_index(op.f("ix_operation_block_id"), "operation", ["block_id"], unique=False)

    product_unit = postgresql.ENUM(
        "kg",
        "g",
        "l",
        "ml",
        "unit",
        name="product_unit",
        create_type=False,
    )
    op.create_table(
        "operation_product",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("operation_id", sa.UUID(), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.Column("rate", sa.Numeric(), nullable=False),
        sa.Column("rate_unit", product_unit, nullable=False),
        sa.Column(
            "rate_basis",
            sa.Enum("per_ha", "per_100l", "per_block", name="rate_basis"),
            nullable=False,
        ),
        sa.Column("water_l_ha", sa.Numeric(), nullable=True),
        sa.Column("total_qty", sa.Numeric(), nullable=False),
        sa.Column("total_unit", product_unit, nullable=False),
        sa.ForeignKeyConstraint(
            ["operation_id"],
            ["operation.id"],
            name=op.f("fk_operation_product_operation_id_operation"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["product.id"],
            name=op.f("fk_operation_product_product_id_product"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_operation_product")),
    )
    op.create_index(
        op.f("ix_operation_product_operation_id"),
        "operation_product",
        ["operation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_operation_product_product_id"),
        "operation_product",
        ["product_id"],
        unique=False,
    )

    op.create_table(
        "operation_safety",
        sa.Column("operation_id", sa.UUID(), nullable=False),
        sa.Column("preharvest_interval_days", sa.Integer(), nullable=True),
        sa.Column("reentry_h", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["operation_id"],
            ["operation.id"],
            name=op.f("fk_operation_safety_operation_id_operation"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("operation_id", name=op.f("pk_operation_safety")),
    )


def downgrade() -> None:
    op.drop_table("operation_safety")
    op.drop_index(op.f("ix_operation_product_product_id"), table_name="operation_product")
    op.drop_index(op.f("ix_operation_product_operation_id"), table_name="operation_product")
    op.drop_table("operation_product")
    op.drop_index(op.f("ix_operation_block_id"), table_name="operation")
    op.drop_index(op.f("ix_operation_farm_id"), table_name="operation")
    op.drop_table("operation")
    op.drop_index(op.f("ix_product_farm_id"), table_name="product")
    op.drop_table("product")
    sa.Enum(name="rate_basis").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="operation_type").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="product_unit").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="product_kind").drop(op.get_bind(), checkfirst=True)
