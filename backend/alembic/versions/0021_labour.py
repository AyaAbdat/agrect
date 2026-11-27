"""labour

Revision ID: 0021
Revises: 0020
Create Date: 2026-11-27 20:49:13.764985

"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "worker",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("farm_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "role",
            sa.Enum(
                "farm_manager",
                "agronomist",
                "irrigation_lead",
                "scout",
                "operator",
                "owner",
                "other",
                name="worker_role",
            ),
            nullable=False,
        ),
        sa.Column("kind", sa.Enum("permanent", "seasonal", name="worker_kind"), nullable=False),
        sa.Column("phone", sa.String(length=64), nullable=True),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
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
            ["farm_id"], ["farm.id"], name=op.f("fk_worker_farm_id_farm"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_worker")),
        sa.UniqueConstraint("farm_id", "name", name="uq_worker_farm_id_name"),
    )
    op.create_index(op.f("ix_worker_farm_id"), "worker", ["farm_id"], unique=False)
    op.create_table(
        "attendance",
        sa.Column("worker_id", sa.UUID(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("farm_id", sa.UUID(), nullable=False),
        sa.Column("present", sa.Boolean(), nullable=False),
        sa.Column("hours", sa.Numeric(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "hours IS NULL OR hours >= 0", name=op.f("ck_attendance_hours_non_negative")
        ),
        sa.ForeignKeyConstraint(
            ["farm_id"], ["farm.id"], name=op.f("fk_attendance_farm_id_farm"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["worker_id"],
            ["worker.id"],
            name=op.f("fk_attendance_worker_id_worker"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("worker_id", "date", name=op.f("pk_attendance")),
    )
    op.create_index(op.f("ix_attendance_farm_id"), "attendance", ["farm_id"], unique=False)
    op.create_table(
        "labour_log",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("farm_id", sa.UUID(), nullable=False),
        sa.Column("operation_id", sa.UUID(), nullable=False),
        sa.Column(
            "worker_ids",
            postgresql.ARRAY(sa.UUID()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column("headcount", sa.Integer(), nullable=True),
        sa.Column("hours_each", sa.Numeric(), nullable=False),
        sa.Column("total_hours", sa.Numeric(), nullable=False),
        sa.CheckConstraint(
            "headcount IS NULL OR headcount >= 0", name=op.f("ck_labour_log_headcount_non_negative")
        ),
        sa.CheckConstraint("hours_each >= 0", name=op.f("ck_labour_log_hours_each_non_negative")),
        sa.ForeignKeyConstraint(
            ["farm_id"], ["farm.id"], name=op.f("fk_labour_log_farm_id_farm"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["operation_id"],
            ["operation.id"],
            name=op.f("fk_labour_log_operation_id_operation"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_labour_log")),
        sa.UniqueConstraint("operation_id", name=op.f("uq_labour_log_operation_id")),
    )
    op.create_index(op.f("ix_labour_log_farm_id"), "labour_log", ["farm_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_labour_log_farm_id"), table_name="labour_log")
    op.drop_table("labour_log")
    op.drop_index(op.f("ix_attendance_farm_id"), table_name="attendance")
    op.drop_table("attendance")
    op.drop_index(op.f("ix_worker_farm_id"), table_name="worker")
    op.drop_table("worker")
    sa.Enum(name="worker_kind").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="worker_role").drop(op.get_bind(), checkfirst=True)
