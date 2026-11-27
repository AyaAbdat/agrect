"""job run

Revision ID: 0023
Revises: 0022
Create Date: 2026-11-27 22:17:07.229336

"""

import sqlalchemy as sa

from alembic import op

revision: str = "0023"
down_revision: str | None = "0022"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "job_run",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("job", sa.String(length=64), nullable=False),
        sa.Column("farm_id", sa.UUID(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.Enum("ok", "error", name="job_status"), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["farm_id"], ["farm.id"], name=op.f("fk_job_run_farm_id_farm"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_job_run")),
    )
    op.create_index(
        "ix_job_run_job_farm_started", "job_run", ["job", "farm_id", "started_at"], unique=False
    )
    op.create_index(op.f("ix_job_run_started_at"), "job_run", ["started_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_job_run_started_at"), table_name="job_run")
    op.drop_index("ix_job_run_job_farm_started", table_name="job_run")
    op.drop_table("job_run")
    sa.Enum(name="job_status").drop(op.get_bind(), checkfirst=True)
