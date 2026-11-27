"""equipment

Revision ID: 0022
Revises: 0021
Create Date: 2026-11-27 21:14:31.192521

"""

import sqlalchemy as sa

from alembic import op

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # New enum values are not used in this transaction, so ADD VALUE is safe here.
    op.execute("ALTER TYPE price_resource ADD VALUE IF NOT EXISTS 'fuel_l'")
    op.execute("ALTER TYPE cost_source ADD VALUE IF NOT EXISTS 'fuel'")
    op.create_table(
        "machine",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("farm_id", sa.UUID(), nullable=False),
        sa.Column(
            "type",
            sa.Enum("tractor", "sprayer", "combine", "other", name="machine_type"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            sa.Enum("ok", "repair", name="machine_status"),
            server_default=sa.text("'ok'"),
            nullable=False,
        ),
        sa.Column("engine_hours_reading", sa.Numeric(), nullable=True),
        sa.Column("reading_date", sa.Date(), nullable=True),
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
            "engine_hours_reading IS NULL OR engine_hours_reading >= 0",
            name=op.f("ck_machine_engine_hours_non_negative"),
        ),
        sa.ForeignKeyConstraint(
            ["farm_id"], ["farm.id"], name=op.f("fk_machine_farm_id_farm"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_machine")),
        sa.UniqueConstraint("farm_id", "name", name="uq_machine_farm_id_name"),
    )
    op.create_index(op.f("ix_machine_farm_id"), "machine", ["farm_id"], unique=False)
    op.create_table(
        "maintenance",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("farm_id", sa.UUID(), nullable=False),
        sa.Column("machine_id", sa.UUID(), nullable=False),
        sa.Column("task", sa.Text(), nullable=False),
        sa.Column("interval_h", sa.Numeric(), nullable=True),
        sa.Column("interval_days", sa.Integer(), nullable=True),
        sa.Column("last_done_date", sa.Date(), nullable=True),
        sa.Column("last_done_h", sa.Numeric(), nullable=True),
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
            "interval_days IS NULL OR interval_days > 0",
            name=op.f("ck_maintenance_interval_days_positive"),
        ),
        sa.CheckConstraint(
            "interval_h IS NOT NULL OR interval_days IS NOT NULL",
            name=op.f("ck_maintenance_interval_required"),
        ),
        sa.CheckConstraint(
            "interval_h IS NULL OR interval_h > 0", name=op.f("ck_maintenance_interval_h_positive")
        ),
        sa.ForeignKeyConstraint(
            ["farm_id"], ["farm.id"], name=op.f("fk_maintenance_farm_id_farm"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["machine_id"],
            ["machine.id"],
            name=op.f("fk_maintenance_machine_id_machine"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_maintenance")),
    )
    op.create_index(op.f("ix_maintenance_farm_id"), "maintenance", ["farm_id"], unique=False)
    op.create_index(op.f("ix_maintenance_machine_id"), "maintenance", ["machine_id"], unique=False)
    op.create_table(
        "machine_use",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("farm_id", sa.UUID(), nullable=False),
        sa.Column("operation_id", sa.UUID(), nullable=False),
        sa.Column("machine_id", sa.UUID(), nullable=False),
        sa.Column("hours", sa.Numeric(), nullable=False),
        sa.Column("fuel_l", sa.Numeric(), nullable=True),
        sa.CheckConstraint(
            "fuel_l IS NULL OR fuel_l >= 0", name=op.f("ck_machine_use_fuel_non_negative")
        ),
        sa.CheckConstraint("hours > 0", name=op.f("ck_machine_use_hours_positive")),
        sa.ForeignKeyConstraint(
            ["farm_id"], ["farm.id"], name=op.f("fk_machine_use_farm_id_farm"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["machine_id"], ["machine.id"], name=op.f("fk_machine_use_machine_id_machine")
        ),
        sa.ForeignKeyConstraint(
            ["operation_id"],
            ["operation.id"],
            name=op.f("fk_machine_use_operation_id_operation"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_machine_use")),
        sa.UniqueConstraint("operation_id", "machine_id", name="uq_machine_use_operation_machine"),
    )
    op.create_index(op.f("ix_machine_use_farm_id"), "machine_use", ["farm_id"], unique=False)
    op.create_index(op.f("ix_machine_use_machine_id"), "machine_use", ["machine_id"], unique=False)
    op.create_index(
        op.f("ix_machine_use_operation_id"), "machine_use", ["operation_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_machine_use_operation_id"), table_name="machine_use")
    op.drop_index(op.f("ix_machine_use_machine_id"), table_name="machine_use")
    op.drop_index(op.f("ix_machine_use_farm_id"), table_name="machine_use")
    op.drop_table("machine_use")
    op.drop_index(op.f("ix_maintenance_machine_id"), table_name="maintenance")
    op.drop_index(op.f("ix_maintenance_farm_id"), table_name="maintenance")
    op.drop_table("maintenance")
    op.drop_index(op.f("ix_machine_farm_id"), table_name="machine")
    op.drop_table("machine")
    sa.Enum(name="machine_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="machine_type").drop(op.get_bind(), checkfirst=True)
    # Postgres cannot drop enum values: fuel_l / fuel stay on price_resource / cost_source;
    # remove rows that use them so older code never reads them.
    op.execute("DELETE FROM cost_line WHERE source = 'fuel'")
    op.execute("DELETE FROM price WHERE resource = 'fuel_l'")
