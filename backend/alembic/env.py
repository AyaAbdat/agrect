from functools import lru_cache
from logging.config import fileConfig

from geoalchemy2 import alembic_helpers
from sqlalchemy import engine_from_config, pool, text

import app.core.models  # noqa: F401
from alembic import context
from app.core.config import get_settings
from app.core.db import Base, engine

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

_EXCLUDED_SCHEMAS = frozenset({"tiger", "tiger_data", "topology"})


@lru_cache
def _visible_schema_by_relname() -> dict[str, str]:
    # PostGIS puts tiger/topology on search_path, so Alembic reflects those
    # relations with schema=None. Map each visible name back to its schema.
    statement = text(
        "SELECT c.relname, n.nspname "
        "FROM pg_class c "
        "JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE pg_table_is_visible(c.oid) "
        "AND n.nspname <> current_schema()"
    )
    with engine.connect() as connection:
        rows = connection.execute(statement)
        return {relname: namespace for relname, namespace in rows}


def _schema_name(obj: object, name: str | None) -> str | None:
    schema = getattr(obj, "schema", None)
    if isinstance(schema, str):
        return schema
    table = getattr(obj, "table", None)
    if table is not None:
        table_schema = getattr(table, "schema", None)
        if isinstance(table_schema, str):
            return table_schema
        table_name = getattr(table, "name", None)
        if isinstance(table_name, str):
            return _visible_schema_by_relname().get(table_name)
    if name is None:
        return None
    return _visible_schema_by_relname().get(name)


def include_object(
    obj: object,
    name: str | None,
    type_: str,
    reflected: bool,
    compare_to: object,
) -> bool:
    if type_ == "table" and name == "spatial_ref_sys":
        return False
    if _schema_name(obj, name) in _EXCLUDED_SCHEMAS:
        return False
    return bool(alembic_helpers.include_object(obj, name, type_, reflected, compare_to))


def run_migrations_offline() -> None:
    context.configure(
        url=get_settings().database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        render_item=alembic_helpers.render_item,
        process_revision_directives=alembic_helpers.writer,
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_settings().database_url
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            render_item=alembic_helpers.render_item,
            process_revision_directives=alembic_helpers.writer,
            include_object=include_object,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
