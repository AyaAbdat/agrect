import threading
import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.auth.models import AppUser
from app.modules.catalog.models import Crop, CropKind
from app.modules.farms.models import Farm
from app.modules.weather import service as weather_service
from app.modules.weather.client import ArchiveDay, HourlyObservation
from app.modules.weather.models import HistoryDaily
from app.modules.weather.service import history_average, history_bounds


def _owned(
    db: Session,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
    email: str,
) -> tuple[Farm, dict[str, str]]:
    user = make_user(email, "password-history")
    farm = make_farm(user, "History farm", Decimal("36.5"), Decimal("3.2"))
    farm.timezone = "Africa/Algiers"
    db.commit()
    return farm, auth_header(user)


def _olive(db: Session) -> Crop:
    crop = Crop(
        code="olive-history",
        kind=CropKind.perennial,
        sort=1,
        name_fr="Olivier",
        name_ar="زيتون",
        name_en="Olive",
    )
    db.add(crop)
    db.commit()
    db.refresh(crop)
    return crop


def _days(start: date, end: date) -> list[ArchiveDay]:
    rows: list[ArchiveDay] = []
    cursor = start
    while cursor <= end:
        rows.append(
            ArchiveDay(
                day=cursor,
                tmin_c=Decimal("1.5"),
                tmax_c=Decimal("16.5"),
                rain_mm=Decimal("0.2"),
                et0_mm=Decimal("3"),
            )
        )
        cursor += timedelta(days=1)
    return rows


def _install_archive(monkeypatch) -> list[tuple[date, date]]:
    calls: list[tuple[date, date]] = []

    def fake(
        _latitude: Decimal,
        _longitude: Decimal,
        start: date,
        end: date,
        _timezone: str,
    ) -> list[ArchiveDay]:
        calls.append((start, end))
        return _days(start, end)

    monkeypatch.setattr("app.modules.weather.service.fetch_archive", fake)
    monkeypatch.setattr(get_settings(), "history_years", 1)
    return calls


def test_history_status_empty_then_idempotent_backfill(
    client: TestClient,
    db: Session,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
    monkeypatch,
) -> None:
    farm, headers = _owned(db, make_user, make_farm, auth_header, "history@agrect.app")
    empty = client.get(f"/v1/farms/{farm.id}/weather/history/status", headers=headers)
    assert empty.status_code == 200
    assert empty.json() == {
        "years": [],
        "from": None,
        "to": None,
        "days": 0,
        "last_fetched_at": None,
        "status": "empty",
    }

    calls = _install_archive(monkeypatch)
    first = client.post(f"/v1/farms/{farm.id}/weather/history/backfill", headers=headers)
    assert first.status_code == 200
    body = first.json()
    start, end = history_bounds(farm)
    assert calls
    assert body["status"] == "ready"
    assert body["from"] == start.isoformat()
    assert body["to"] == end.isoformat()
    assert body["days"] == (end - start).days + 1
    assert body["last_fetched_at"] is not None
    expected_years = [
        year
        for year in range(start.year, end.year + 1)
        if (min(end, date(year, 12, 31)) - max(start, date(year, 1, 1))).days + 1 >= 360
    ]
    assert body["years"] == expected_years
    assert calls == [
        (max(start, date(year, 1, 1)), min(end, date(year, 12, 31)))
        for year in range(start.year, end.year + 1)
    ]
    stored = db.scalar(
        select(func.count()).select_from(HistoryDaily).where(HistoryDaily.farm_id == farm.id)
    )
    assert stored == body["days"]
    sample = db.scalars(
        select(HistoryDaily).where(HistoryDaily.farm_id == farm.id).limit(1)
    ).first()
    assert sample is not None
    assert sample.source == "estimated"
    assert sample.tmin_c == Decimal("1.5")
    assert sample.tmax_c == Decimal("16.5")
    assert sample.fetched_at.tzinfo is not None

    calls.clear()
    second = client.post(f"/v1/farms/{farm.id}/weather/history/backfill", headers=headers)
    assert second.status_code == 200
    assert second.json()["days"] == body["days"]
    assert calls == []

    missing_year = expected_years[0]
    calls.clear()
    db.execute(
        delete(HistoryDaily).where(
            HistoryDaily.farm_id == farm.id,
            HistoryDaily.date >= date(missing_year, 1, 1),
            HistoryDaily.date <= date(missing_year, 12, 31),
        )
    )
    db.commit()
    third = client.post(f"/v1/farms/{farm.id}/weather/history/backfill", headers=headers)
    assert third.status_code == 200
    assert calls == [(date(missing_year, 1, 1), date(missing_year, 12, 31))]


def test_incomplete_years_are_excluded(
    client: TestClient,
    db: Session,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm, headers = _owned(db, make_user, make_farm, auth_header, "years@agrect.app")
    fetched_at = datetime(2026, 1, 1, tzinfo=UTC)
    rows = [
        HistoryDaily(
            farm_id=farm.id,
            date=date(2019, 1, 1) + timedelta(days=offset),
            tmin_c=Decimal("1"),
            tmax_c=Decimal("10"),
            source="estimated",
            fetched_at=fetched_at,
        )
        for offset in range(360)
    ]
    rows.extend(
        HistoryDaily(
            farm_id=farm.id,
            date=date(2020, 1, 1) + timedelta(days=offset),
            tmin_c=Decimal("1"),
            tmax_c=Decimal("10"),
            source="estimated",
            fetched_at=fetched_at,
        )
        for offset in range(359)
    )
    db.add_all(rows)
    db.commit()
    status = client.get(f"/v1/farms/{farm.id}/weather/history/status", headers=headers)
    assert status.status_code == 200
    assert status.json()["years"] == [2019]
    assert status.json()["days"] == 719
    assert status.json()["status"] == "ready"


def test_history_average_uses_28_february_and_stays_on_the_farm(
    db: Session,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
) -> None:
    owner = make_user("avg@agrect.app", "password-history")
    farm = make_farm(owner, "Average farm", Decimal("36.5"), Decimal("3.2"))
    other_owner = make_user("avg-other@agrect.app", "password-history")
    other = make_farm(other_owner, "Other farm", Decimal("36.5"), Decimal("3.2"))
    fetched_at = datetime(2026, 3, 1, tzinfo=UTC)

    def add(target: Farm, day: date, tmin: str, tmax: str) -> None:
        db.add(
            HistoryDaily(
                farm_id=target.id,
                date=day,
                tmin_c=Decimal(tmin),
                tmax_c=Decimal(tmax),
                source="estimated",
                fetched_at=fetched_at,
            )
        )

    add(farm, date(2024, 2, 29), "1", "11")
    add(farm, date(2024, 2, 28), "9", "19")
    add(farm, date(2023, 2, 28), "3", "13")
    add(other, date(2024, 2, 29), "100", "100")
    db.commit()
    averaged = history_average(db, farm, date(2024, 2, 29))
    assert averaged.tmin_c == Decimal("2")
    assert averaged.tmax_c == Decimal("12")


def test_degree_days_history_loading(
    client: TestClient,
    db: Session,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
    monkeypatch,
) -> None:
    farm, headers = _owned(db, make_user, make_farm, auth_header, "loading@agrect.app")
    crop = _olive(db)
    monkeypatch.setattr(weather_service, "HISTORY_ENSURE_TIMEOUT_S", 0.5)
    release = threading.Event()

    def slow(*_args: object, **_kwargs: object) -> list[ArchiveDay]:
        release.wait(3)
        return []

    now = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    hour = HourlyObservation(
        ts=now,
        temp_c=Decimal("10"),
        rh_pct=Decimal("50"),
        rain_mm=Decimal("0"),
        rain_prob_pct=None,
        wind_ms=Decimal("1"),
        gust_ms=Decimal("1"),
        wind_dir_deg=Decimal("0"),
        rad_wm2=Decimal("0"),
        et0_mm=Decimal("0.1"),
    )
    monkeypatch.setattr(weather_service, "fetch_archive", slow)
    monkeypatch.setattr(weather_service, "fetch_forecast", lambda _lat, _lon: [hour])
    response = client.get(
        f"/v1/farms/{farm.id}/weather/degree-days",
        headers=headers,
        params={"crop_id": str(crop.id), "from": "2026-01-01"},
    )
    assert response.status_code == 200
    assert response.json()["history_status"] == "loading"
    status = client.get(f"/v1/farms/{farm.id}/weather/history/status", headers=headers)
    assert status.status_code == 200
    assert status.json()["status"] == "loading"
    release.set()
    thread = weather_service._jobs[farm.id]
    thread.join(timeout=3)


def test_history_is_scoped(
    client: TestClient,
    db: Session,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm, _headers = _owned(db, make_user, make_farm, auth_header, "owner-hist@agrect.app")
    stranger = make_user("stranger-hist@agrect.app", "password-history")
    headers = auth_header(stranger)
    status = client.get(f"/v1/farms/{farm.id}/weather/history/status", headers=headers)
    assert status.status_code == 404
    assert status.json() == {"code": "farm.not_found"}
    denied = client.post(f"/v1/farms/{farm.id}/weather/history/backfill", headers=headers)
    assert denied.status_code == 404
    assert denied.json() == {"code": "farm.not_found"}
    missing = client.get(
        f"/v1/farms/{uuid.uuid4()}/weather/history/status",
        headers=headers,
    )
    assert missing.status_code == 404
    assert missing.json() == {"code": "farm.not_found"}
