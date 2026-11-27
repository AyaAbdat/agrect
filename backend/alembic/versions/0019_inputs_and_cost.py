"""inputs and cost

Revision ID: 0019
Revises: 0018
Create Date: 2026-11-24 12:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "price",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("farm_id", sa.UUID(), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=True),
        sa.Column(
            "resource",
            sa.Enum(
                "product",
                "water_m3",
                "labour_h",
                "machine_h",
                "energy_kwh",
                name="price_resource",
            ),
            nullable=False,
        ),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("dzd_per_unit", sa.Numeric(), nullable=False),
        sa.Column("unit", sa.String(length=16), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
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
        sa.CheckConstraint("dzd_per_unit > 0", name="ck_price_dzd_per_unit_positive"),
        sa.ForeignKeyConstraint(
            ["farm_id"],
            ["farm.id"],
            name=op.f("fk_price_farm_id_farm"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["product.id"],
            name=op.f("fk_price_product_id_product"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_price")),
    )
    op.create_index(op.f("ix_price_farm_id"), "price", ["farm_id"], unique=False)
    op.create_index(op.f("ix_price_product_id"), "price", ["product_id"], unique=False)

    op.create_table(
        "stock_move",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("farm_id", sa.UUID(), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("qty", sa.Numeric(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum("purchase", "use", "adjustment", name="stock_move_kind"),
            nullable=False,
        ),
        sa.Column("operation_id", sa.UUID(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
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
            name=op.f("fk_stock_move_farm_id_farm"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["product.id"],
            name=op.f("fk_stock_move_product_id_product"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["operation_id"],
            ["operation.id"],
            name=op.f("fk_stock_move_operation_id_operation"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app_user.id"],
            name=op.f("fk_stock_move_user_id_app_user"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stock_move")),
    )
    op.create_index(op.f("ix_stock_move_farm_id"), "stock_move", ["farm_id"], unique=False)
    op.create_index(op.f("ix_stock_move_product_id"), "stock_move", ["product_id"], unique=False)
    op.create_index(
        op.f("ix_stock_move_operation_id"), "stock_move", ["operation_id"], unique=False
    )

    op.create_table(
        "cost_line",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("farm_id", sa.UUID(), nullable=False),
        sa.Column("block_id", sa.UUID(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column(
            "source",
            sa.Enum("product", "labour", "machine", "water", "energy", name="cost_source"),
            nullable=False,
        ),
        sa.Column(
            "ref_kind",
            sa.Enum("operation", "irrigation", name="cost_ref_kind"),
            nullable=False,
        ),
        sa.Column("ref_id", sa.UUID(), nullable=False),
        sa.Column("qty", sa.Numeric(), nullable=False),
        sa.Column("unit", sa.String(length=16), nullable=False),
        sa.Column("dzd", sa.Numeric(), nullable=False),
        sa.Column("price_id", sa.UUID(), nullable=True),
        sa.Column("inputs_hash", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(
            ["farm_id"],
            ["farm.id"],
            name=op.f("fk_cost_line_farm_id_farm"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["block_id"],
            ["block.id"],
            name=op.f("fk_cost_line_block_id_block"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["price_id"],
            ["price.id"],
            name=op.f("fk_cost_line_price_id_price"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cost_line")),
    )
    op.create_index(op.f("ix_cost_line_farm_id"), "cost_line", ["farm_id"], unique=False)
    op.create_index(op.f("ix_cost_line_block_id"), "cost_line", ["block_id"], unique=False)
    op.create_index(op.f("ix_cost_line_ref_id"), "cost_line", ["ref_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_cost_line_ref_id"), table_name="cost_line")
    op.drop_index(op.f("ix_cost_line_block_id"), table_name="cost_line")
    op.drop_index(op.f("ix_cost_line_farm_id"), table_name="cost_line")
    op.drop_table("cost_line")
    op.drop_index(op.f("ix_stock_move_operation_id"), table_name="stock_move")
    op.drop_index(op.f("ix_stock_move_product_id"), table_name="stock_move")
    op.drop_index(op.f("ix_stock_move_farm_id"), table_name="stock_move")
    op.drop_table("stock_move")
    op.drop_index(op.f("ix_price_product_id"), table_name="price")
    op.drop_index(op.f("ix_price_farm_id"), table_name="price")
    op.drop_table("price")
    sa.Enum(name="cost_ref_kind").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="cost_source").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="stock_move_kind").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="price_resource").drop(op.get_bind(), checkfirst=True)
