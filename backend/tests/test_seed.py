from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.core.security import verify_password
from app.modules.auth.models import AppUser
from app.modules.farms.models import Farm, WeatherSource
from app.modules.farms.service import read_lat_lon
from app.seed import main


def test_seed_twice(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEMO_USER_EMAIL", "seed@agrect.app")
    monkeypatch.setenv("DEMO_USER_PASSWORD", "seed-password")
    monkeypatch.setenv("DEMO_FARM_NAME", "Seed farm")
    monkeypatch.setenv("DEMO_FARM_LAT", "36.500000")
    monkeypatch.setenv("DEMO_FARM_LON", "3.250000")
    monkeypatch.setenv("DEMO_FARM_TZ", "Africa/Algiers")
    get_settings.cache_clear()
    try:
        main()
        with SessionLocal() as session:
            first_hash = session.scalar(select(AppUser.password_hash))
        main()
        with SessionLocal() as session:
            _assert_one_seed(session, first_hash)
    finally:
        get_settings.cache_clear()


def _assert_one_seed(session: Session, first_hash: object) -> None:
    users = session.scalars(select(AppUser)).all()
    farms = session.scalars(select(Farm)).all()
    assert len(users) == 1
    assert len(farms) == 1
    assert users[0].email == "seed@agrect.app"
    assert users[0].password_hash == first_hash
    assert verify_password("seed-password", users[0].password_hash)
    assert farms[0].name == "Seed farm"
    assert farms[0].owner_user_id == users[0].id
    assert farms[0].timezone == "Africa/Algiers"
    assert farms[0].weather_source == WeatherSource.service
    lat, lon = read_lat_lon(session, farms[0])
    assert lat == Decimal("36.5")
    assert lon == Decimal("3.25")
