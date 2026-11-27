# ruff: noqa: E402
"""Point tests at agrect_test before the application (and its engine) is imported."""

import os
from collections.abc import Callable, Generator
from decimal import Decimal
from pathlib import Path

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy import create_engine, text
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from alembic import command

_BACKEND_DIR = Path(__file__).resolve().parents[1]
_REPO_ROOT = _BACKEND_DIR.parent


def _configured_database_url() -> str:
    env_url = os.environ.get("DATABASE_URL")
    if env_url:
        return env_url
    chosen: str | None = None
    for raw_line in (_REPO_ROOT / ".env").read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == "DATABASE_URL":
            chosen = value.strip().strip('"').strip("'")
    if not chosen:
        raise RuntimeError("DATABASE_URL is not set")
    return chosen


os.environ["JWT_SECRET"] = "test-secret-" + "0" * 52
# Minimal argon2 cost in tests only (app.core.security); production keeps the defaults.
os.environ["TEST_FAST_HASH"] = "1"
os.environ["DATABASE_URL"] = (
    make_url(_configured_database_url())
    .set(database="agrect_test")
    .render_as_string(hide_password=False)
)

from app.core.config import get_settings
from app.modules.weather.client import WeatherProviderError

get_settings.cache_clear()

from app.core.db import Base, SessionLocal, engine
from app.core.security import create_access_token, hash_password
from app.main import app
from app.modules.auth.models import AppUser
from app.modules.farms.models import Farm
from app.modules.farms.service import location_point

if engine.url.database != "agrect_test":
    raise RuntimeError("tests must use the agrect_test database")


def _ensure_test_database() -> None:
    admin_url = make_url(os.environ["DATABASE_URL"]).set(database="postgres")
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT", poolclass=NullPool)
    try:
        with admin_engine.connect() as connection:
            exists = connection.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = 'agrect_test'")
            )
            if exists is None:
                connection.execute(text("CREATE DATABASE agrect_test"))
    finally:
        admin_engine.dispose()


def _app_tables() -> list[str]:
    """Every application table, children before parents (safe DELETE order)."""
    import app.core.models  # noqa: F401  (registers every model on the metadata)

    return [table.name for table in reversed(Base.metadata.sorted_tables)]


def _check_reset_covers_database(tables: list[str]) -> None:
    """Fail loudly if a table exists in the database but would not be reset."""
    with engine.connect() as connection:
        present = set(
            connection.scalars(
                text(
                    "SELECT tablename FROM pg_tables WHERE schemaname = 'public' "
                    "AND tablename NOT IN ('alembic_version', 'spatial_ref_sys')"
                )
            )
        )
    missing = present - set(tables)
    if missing:
        raise RuntimeError(f"tables not reset between tests: {sorted(missing)}")


def _reset_test_tables() -> None:
    """Empty every application table in one round trip.

    One batch of DELETE statements (children first) instead of TRUNCATE: TRUNCATE
    recreates each table's files and costs seconds per test on a Docker volume,
    while DELETE on these small tables takes milliseconds. No table uses a
    sequence (UUID keys), so RESTART IDENTITY has nothing to reset.
    """
    if engine.url.database != "agrect_test":
        raise RuntimeError("refusing to reset a non-test database")
    batch = sql.SQL("; ").join(
        sql.SQL("DELETE FROM {}").format(sql.Identifier(name)) for name in _TABLES
    )
    with engine.begin() as connection:
        with connection.connection.cursor() as cursor:
            cursor.execute(batch)


_TABLES = _app_tables()


@pytest.fixture(scope="session", autouse=True)
def _prepare_test_database() -> None:
    _ensure_test_database()
    cfg = Config(str(_BACKEND_DIR / "alembic.ini"))
    command.upgrade(cfg, "head")
    _check_reset_covers_database(_TABLES)
    _reset_test_tables()


@pytest.fixture(autouse=True)
def _clean_tables() -> Generator[None, None, None]:
    yield
    _reset_test_tables()


@pytest.fixture(autouse=True)
def _block_archive_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Degree-day reads must not call the real archive while history is empty."""

    def _blocked(*_args: object, **_kwargs: object) -> list[object]:
        raise WeatherProviderError("archive disabled in tests")

    monkeypatch.setattr("app.modules.weather.service.fetch_archive", _blocked)


@pytest.fixture(autouse=True)
def _join_history_workers() -> Generator[None, None, None]:
    yield
    from app.modules.weather.service import _jobs

    for thread in list(_jobs.values()):
        thread.join(timeout=5)


@pytest.fixture
def db() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def make_user(db: Session) -> Callable[[str, str], AppUser]:
    def _make(email: str, password: str) -> AppUser:
        user = AppUser(email=email, password_hash=hash_password(password))
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    return _make


@pytest.fixture
def make_farm(db: Session) -> Callable[[AppUser, str, Decimal, Decimal], Farm]:
    def _make(owner: AppUser, name: str, lat: Decimal, lon: Decimal) -> Farm:
        farm = Farm(owner_user_id=owner.id, name=name)
        farm.location = location_point(lon, lat)
        db.add(farm)
        db.commit()
        db.refresh(farm)
        return farm

    return _make


@pytest.fixture
def auth_header() -> Callable[[AppUser], dict[str, str]]:
    def _header(user: AppUser) -> dict[str, str]:
        return {"Authorization": f"Bearer {create_access_token(user.id)}"}

    return _header
