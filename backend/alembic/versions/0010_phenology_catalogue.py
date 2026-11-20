"""phenology catalogue

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-20 17:01:21.878911

"""

import sqlalchemy as sa

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "crop_scale",
        sa.Column("crop_id", sa.UUID(), nullable=False),
        sa.Column(
            "scale",
            sa.Enum("el", "bbch", "bbch_olive", "zadoks", name="crop_scale_code"),
            nullable=False,
        ),
        sa.Column("citation", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["crop_id"],
            ["crop.id"],
            name=op.f("fk_crop_scale_crop_id_crop"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("crop_id", name=op.f("pk_crop_scale")),
    )
    op.create_table(
        "stage_def",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("crop_id", sa.UUID(), nullable=False),
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column("sort", sa.Integer(), nullable=False),
        sa.Column("name_fr", sa.String(length=255), nullable=False),
        sa.Column("name_ar", sa.String(length=255), nullable=False),
        sa.Column("name_en", sa.String(length=255), nullable=False),
        sa.Column("description_fr", sa.Text(), nullable=False),
        sa.Column("description_ar", sa.Text(), nullable=False),
        sa.Column("description_en", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["crop_id"],
            ["crop.id"],
            name=op.f("fk_stage_def_crop_id_crop"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stage_def")),
        sa.UniqueConstraint("crop_id", "code", name=op.f("uq_stage_def_crop_id")),
    )
    op.create_index(op.f("ix_stage_def_crop_id"), "stage_def", ["crop_id"], unique=False)
    op.create_table(
        "farm_stage_pref",
        sa.Column("farm_id", sa.UUID(), nullable=False),
        sa.Column("stage_def_id", sa.UUID(), nullable=False),
        sa.Column("hidden", sa.Boolean(), nullable=False),
        sa.Column("local_name", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(
            ["farm_id"],
            ["farm.id"],
            name=op.f("fk_farm_stage_pref_farm_id_farm"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["stage_def_id"],
            ["stage_def.id"],
            name=op.f("fk_farm_stage_pref_stage_def_id_stage_def"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("farm_id", "stage_def_id", name=op.f("pk_farm_stage_pref")),
    )
    op.create_table(
        "stage_dd",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("crop_id", sa.UUID(), nullable=False),
        sa.Column("variety_id", sa.UUID(), nullable=True),
        sa.Column("stage_def_id", sa.UUID(), nullable=False),
        sa.Column("dd_value", sa.Numeric(), nullable=False),
        sa.Column("base_c", sa.Numeric(), nullable=False),
        sa.Column("upper_c", sa.Numeric(), nullable=True),
        sa.Column(
            "method",
            sa.Enum("average", "single_sine", name="gdd_method", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "source_kind",
            sa.Enum("literature", "farm_seasons", "entered", name="stage_dd_source"),
            nullable=False,
        ),
        sa.Column("citation", sa.Text(), nullable=True),
        sa.Column("farm_id", sa.UUID(), nullable=True),
        sa.CheckConstraint(
            "(farm_id IS NULL AND citation IS NOT NULL AND btrim(citation) <> '' "
            "AND source_kind <> 'entered') "
            "OR (farm_id IS NOT NULL AND source_kind = 'entered')",
            name=op.f("ck_stage_dd_global_cited_or_farm_entered"),
        ),
        sa.CheckConstraint("dd_value > 0", name=op.f("ck_stage_dd_dd_must_be_positive")),
        sa.ForeignKeyConstraint(
            ["crop_id"],
            ["crop.id"],
            name=op.f("fk_stage_dd_crop_id_crop"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["farm_id"],
            ["farm.id"],
            name=op.f("fk_stage_dd_farm_id_farm"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["stage_def_id"],
            ["stage_def.id"],
            name=op.f("fk_stage_dd_stage_def_id_stage_def"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["variety_id"],
            ["variety.id"],
            name=op.f("fk_stage_dd_variety_id_variety"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stage_dd")),
    )
    op.create_index(op.f("ix_stage_dd_crop_id"), "stage_dd", ["crop_id"], unique=False)
    op.create_index(op.f("ix_stage_dd_farm_id"), "stage_dd", ["farm_id"], unique=False)
    op.create_index(
        "uq_stage_dd_farm_stage",
        "stage_dd",
        ["farm_id", "stage_def_id"],
        unique=True,
        postgresql_where=sa.text("farm_id IS NOT NULL"),
    )
    op.create_index(
        "uq_stage_dd_global_stage",
        "stage_dd",
        ["stage_def_id"],
        unique=True,
        postgresql_where=sa.text("farm_id IS NULL AND variety_id IS NULL"),
    )
    op.create_index(
        "uq_stage_dd_variety_stage",
        "stage_dd",
        ["variety_id", "stage_def_id"],
        unique=True,
        postgresql_where=sa.text("variety_id IS NOT NULL AND farm_id IS NULL"),
    )
    op.create_table(
        "variety_chill",
        sa.Column("variety_id", sa.UUID(), nullable=False),
        sa.Column("chill_h", sa.Numeric(), nullable=True),
        sa.Column("chill_portions", sa.Numeric(), nullable=True),
        sa.Column("citation", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["variety_id"],
            ["variety.id"],
            name=op.f("fk_variety_chill_variety_id_variety"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("variety_id", name=op.f("pk_variety_chill")),
    )


def downgrade() -> None:
    op.drop_table("variety_chill")
    op.drop_index(
        "uq_stage_dd_variety_stage",
        table_name="stage_dd",
        postgresql_where=sa.text("variety_id IS NOT NULL AND farm_id IS NULL"),
    )
    op.drop_index(
        "uq_stage_dd_global_stage",
        table_name="stage_dd",
        postgresql_where=sa.text("farm_id IS NULL AND variety_id IS NULL"),
    )
    op.drop_index(
        "uq_stage_dd_farm_stage",
        table_name="stage_dd",
        postgresql_where=sa.text("farm_id IS NOT NULL"),
    )
    op.drop_index(op.f("ix_stage_dd_farm_id"), table_name="stage_dd")
    op.drop_index(op.f("ix_stage_dd_crop_id"), table_name="stage_dd")
    op.drop_table("stage_dd")
    op.drop_table("farm_stage_pref")
    op.drop_index(op.f("ix_stage_def_crop_id"), table_name="stage_def")
    op.drop_table("stage_def")
    op.drop_table("crop_scale")
    sa.Enum("literature", "farm_seasons", "entered", name="stage_dd_source").drop(
        op.get_bind(),
        checkfirst=False,
    )
    sa.Enum("el", "bbch", "bbch_olive", "zadoks", name="crop_scale_code").drop(
        op.get_bind(),
        checkfirst=False,
    )
