import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.modules.auth.models import AppUser
from app.modules.catalog.models import Crop, CropKind
from app.modules.farms.models import Farm
from app.modules.weather.calc import radiation_sum_jcm2
from app.modules.weather.client import HourlyObservation, WeatherProviderError
from app.modules.weather.models import WeatherDaily, WeatherHourly

ZONE = ZoneInfo("Africa/Algiers")


def _point(
    ts: datetime,
    temp: Decimal,
    *,
    rh: Decimal | None = Decimal("50"),
    rain: Decimal | None = Decimal("0"),
    rain_prob: Decimal | None = None,
    et0: Decimal | None = Decimal("0.1"),
    rad: Decimal | None = Decimal("0"),
) -> HourlyObservation:
    return HourlyObservation(
        ts=ts,
        temp_c=temp,
        rh_pct=rh,
        rain_mm=rain,
        rain_prob_pct=rain_prob,
        wind_ms=Decimal("1.5"),
        gust_ms=Decimal("3"),
        wind_dir_deg=Decimal("180"),
        rad_wm2=rad,
        et0_mm=et0,
    )


def _local(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=ZONE).astimezone(UTC)


class _Feed:
    def __init__(self, rows: list[HourlyObservation]) -> None:
        self.rows = rows
        self.fail = False
        self.calls = 0

    def __call__(self, _lat: Decimal, _lon: Decimal) -> list[HourlyObservation]:
        self.calls += 1
        if self.fail:
            raise WeatherProviderError("down")
        return self.rows


def _owned(
    db: Session,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
    email: str = "weather@agrect.app",
) -> tuple[AppUser, Farm, dict[str, str]]:
    user = make_user(email, "password-weather")
    farm = make_farm(user, "Weather farm", Decimal("36.5"), Decimal("3.2"))
    farm.timezone = "Africa/Algiers"
    db.commit()
    return user, farm, auth_header(user)


def _olive(db: Session) -> Crop:
    crop = Crop(
        code="olive",
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


def test_local_day_and_idempotent_refresh(
    client: TestClient,
    db: Session,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
    monkeypatch,
) -> None:
    _user, farm, headers = _owned(db, make_user, make_farm, auth_header)
    anchor = (datetime.now(UTC) - timedelta(days=5)).replace(minute=0, second=0, microsecond=0)
    evening = anchor.replace(hour=22)
    late = anchor.replace(hour=23, minute=30)
    assert evening.astimezone(ZONE).date() == evening.date()
    assert late.astimezone(ZONE).date() == evening.date() + timedelta(days=1)
    feed = _Feed(
        [
            _point(evening, Decimal("11")),
            _point(late, Decimal("4")),
        ]
    )
    monkeypatch.setattr("app.modules.weather.service.fetch_forecast", feed)
    first = client.post(f"/v1/farms/{farm.id}/weather/refresh", headers=headers)
    second = client.post(f"/v1/farms/{farm.id}/weather/refresh", headers=headers)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["hours"] == 2
    assert first.json()["days"] == 2
    assert second.json()["hours"] == 2
    stored = db.scalar(
        select(func.count()).select_from(WeatherHourly).where(WeatherHourly.farm_id == farm.id)
    )
    assert stored == 2
    rows = list(
        db.scalars(
            select(WeatherDaily).where(WeatherDaily.farm_id == farm.id).order_by(WeatherDaily.date)
        ).all()
    )
    assert [row.date for row in rows] == [
        evening.astimezone(ZONE).date(),
        late.astimezone(ZONE).date(),
    ]
    assert rows[0].tmin_c == Decimal("11")
    assert rows[1].tmax_c == Decimal("4")
    assert rows[0].source == "estimated"
    assert len(rows[0].inputs_hash) == 64


def test_null_thresholds_then_rederive(
    client: TestClient,
    db: Session,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
    monkeypatch,
) -> None:
    _user, farm, headers = _owned(db, make_user, make_farm, auth_header, "thresh@agrect.app")
    crop = _olive(db)
    today = datetime.now(UTC).astimezone(ZONE).date()
    past = today - timedelta(days=4)
    future = datetime.now(UTC) + timedelta(hours=2)
    feed = _Feed(
        [
            _point(_local(past, 1), Decimal("-1")),
            _point(_local(past, 2), Decimal("0")),
            _point(_local(past, 3), Decimal("1")),
            _point(_local(past, 4), Decimal("36")),
            _point(future, Decimal("3")),
        ]
    )
    monkeypatch.setattr("app.modules.weather.service.fetch_forecast", feed)
    assert client.post(f"/v1/farms/{farm.id}/weather/refresh", headers=headers).status_code == 200
    daily = client.get(f"/v1/farms/{farm.id}/weather/daily", headers=headers)
    assert daily.status_code == 200
    past_row = next(row for row in daily.json()["days"] if row["date"] == past.isoformat())
    assert past_row["frost_h"] is None
    assert past_row["heat_h"] is None
    assert past_row["chill_h"] is None
    assert past_row["hours_count"] == 4
    assert past_row["source"] == "estimated"

    saved = client.put(
        f"/v1/farms/{farm.id}/thresholds",
        headers=headers,
        json={
            "frost_c": "0",
            "heat_c": "35",
            "vpd_limit_kpa": "1.5",
            "chill_season_start": today.isoformat(),
        },
    )
    assert saved.status_code == 200
    assert saved.json()["frost_c"] == "0"
    assert saved.json()["vpd_limit_kpa"] == "1.5"
    assert saved.json()["chill_season_start"] == today.isoformat()

    daily_after = client.get(f"/v1/farms/{farm.id}/weather/daily", headers=headers)
    past_after = next(row for row in daily_after.json()["days"] if row["date"] == past.isoformat())
    assert past_after["frost_h"] == 2
    assert past_after["heat_h"] == 1
    assert past_after["chill_h"] is None

    degree = client.get(
        f"/v1/farms/{farm.id}/weather/degree-days",
        headers=headers,
        params={"crop_id": str(crop.id), "from": past.isoformat()},
    )
    assert degree.status_code == 200
    body = degree.json()
    assert body["label"] == "not_enough_data"
    assert body["setting"] is None
    assert body["gdd_total"] is None
    assert body["frost_h_total"] == 2
    assert body["heat_h_total"] == 1
    assert body["chill"]["season_start"] == today.isoformat()
    assert body["chill"]["hours_total"] == 1
    by_date = {row["date"]: row for row in body["days"]}
    future_day = future.astimezone(ZONE).date().isoformat()
    assert by_date[past.isoformat()]["is_forecast"] is False
    assert by_date[past.isoformat()]["gdd"] is None
    assert by_date[future_day]["is_forecast"] is True


def test_degree_days_average_and_single_sine(
    client: TestClient,
    db: Session,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
    monkeypatch,
) -> None:
    _user, farm, headers = _owned(db, make_user, make_farm, auth_header, "gdd@agrect.app")
    crop = _olive(db)
    day = datetime.now(UTC).astimezone(ZONE).date() - timedelta(days=3)
    feed = _Feed(
        [
            _point(_local(day, 8), Decimal("14")),
            _point(_local(day, 15), Decimal("30")),
        ]
    )
    monkeypatch.setattr("app.modules.weather.service.fetch_forecast", feed)
    assert client.post(f"/v1/farms/{farm.id}/weather/refresh", headers=headers).status_code == 200
    empty = client.get(
        f"/v1/farms/{farm.id}/gdd-settings/{crop.id}",
        headers=headers,
    )
    assert empty.status_code == 200
    assert empty.json()["base_c"] is None
    assert empty.json()["method"] is None

    params = {"crop_id": str(crop.id), "from": day.isoformat()}
    missing = client.get(f"/v1/farms/{farm.id}/weather/degree-days", headers=headers, params=params)
    assert missing.status_code == 200
    assert missing.json()["label"] == "not_enough_data"
    assert missing.json()["setting"] is None
    assert missing.json()["days"][0]["gdd"] is None
    assert missing.json()["data_from"] == day.isoformat()

    average = client.put(
        f"/v1/farms/{farm.id}/gdd-settings/{crop.id}",
        headers=headers,
        json={"base_c": "10", "method": "average"},
    )
    assert average.status_code == 200
    assert average.json()["method"] == "average"
    assert average.json()["upper_c"] is None

    averaged = client.get(
        f"/v1/farms/{farm.id}/weather/degree-days",
        headers=headers,
        params=params,
    ).json()
    assert averaged["label"] == "calculated"
    assert averaged["setting"]["method"] == "average"
    assert Decimal(averaged["days"][0]["gdd"]) == Decimal("12")
    assert Decimal(averaged["days"][0]["gdd_cum"]) == Decimal("12")
    assert Decimal(averaged["gdd_total"]) == Decimal("12")
    assert averaged["from"] == day.isoformat()

    sine = client.put(
        f"/v1/farms/{farm.id}/gdd-settings/{crop.id}",
        headers=headers,
        json={"base_c": "10", "upper_c": "28", "method": "single_sine"},
    )
    assert sine.status_code == 200
    curved = client.get(
        f"/v1/farms/{farm.id}/weather/degree-days",
        headers=headers,
        params=params,
    ).json()
    assert curved["setting"]["method"] == "single_sine"
    assert Decimal(curved["days"][0]["gdd"]) == Decimal("11.6960")
    assert curved["days"][0]["is_forecast"] is False


def test_forecast_and_today_so_far(
    client: TestClient,
    db: Session,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
    monkeypatch,
) -> None:
    _user, farm, headers = _owned(db, make_user, make_farm, auth_header, "now@agrect.app")
    now = datetime.now(UTC)
    past = now - timedelta(hours=3)
    future = now + timedelta(hours=2)
    old = now - timedelta(days=8)
    feed = _Feed(
        [
            _point(old, Decimal("9"), rain=Decimal("5")),
            _point(past, Decimal("25"), rh=Decimal("50"), rain=Decimal("1.25")),
            _point(future, Decimal("22"), rain=Decimal("9"), rain_prob=Decimal("40")),
        ]
    )
    monkeypatch.setattr("app.modules.weather.service.fetch_forecast", feed)
    assert client.post(f"/v1/farms/{farm.id}/weather/refresh", headers=headers).status_code == 200
    assert feed.calls == 1
    now_response = client.get(f"/v1/farms/{farm.id}/weather/now", headers=headers)
    assert now_response.status_code == 200
    assert feed.calls == 1
    body = now_response.json()
    assert body["provider"] == "Open-Meteo"
    assert body["source"] == "estimated"
    assert body["dewpoint_source"] == "calculated"
    assert body["vpd_source"] == "calculated"
    assert body["stale"] is False
    assert Decimal(body["temp_c"]) == Decimal("25")
    assert isinstance(body["temp_c"], str)
    assert isinstance(body["dewpoint_c"], str)
    today = now.astimezone(ZONE).date()
    today_rain = [
        row.rain_mm
        for row in feed.rows
        if row.ts <= now and row.ts.astimezone(ZONE).date() == today and row.rain_mm is not None
    ]
    if today_rain:
        assert Decimal(body["rain_mm"]) == sum(today_rain, Decimal(0))
        assert Decimal("9") not in today_rain
    else:
        assert body["rain_mm"] is None

    forecast = client.get(f"/v1/farms/{farm.id}/weather/forecast", headers=headers)
    assert forecast.status_code == 200
    forecast_body = forecast.json()
    hourly_temps = [Decimal(row["temp_c"]) for row in forecast_body["hourly"]]
    assert Decimal("22") in hourly_temps
    assert Decimal("25") not in hourly_temps
    assert all(row["date"] >= today.isoformat() for row in forecast_body["daily"])
    future_day = future.astimezone(ZONE).date().isoformat()
    matched = next(row for row in forecast_body["daily"] if row["date"] == future_day)
    assert Decimal(matched["rain_prob_pct"]) == Decimal("40")
    assert matched["source"] == "estimated"
    assert old.astimezone(ZONE).date().isoformat() not in {
        row["date"] for row in forecast_body["daily"]
    }


def test_stale_when_provider_fails(
    client: TestClient,
    db: Session,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
    monkeypatch,
) -> None:
    _user, farm, headers = _owned(db, make_user, make_farm, auth_header, "stale@agrect.app")
    past = datetime.now(UTC) - timedelta(hours=4)
    feed = _Feed([_point(past, Decimal("18"), rh=Decimal("40"))])
    monkeypatch.setattr("app.modules.weather.service.fetch_forecast", feed)
    assert client.post(f"/v1/farms/{farm.id}/weather/refresh", headers=headers).status_code == 200
    backdated = datetime.now(UTC) - timedelta(hours=2)
    db.execute(
        update(WeatherHourly).where(WeatherHourly.farm_id == farm.id).values(issued_at=backdated)
    )
    db.commit()
    feed.fail = True
    response = client.get(f"/v1/farms/{farm.id}/weather/now", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["stale"] is True
    assert Decimal(body["temp_c"]) == Decimal("18")
    assert body["provider"] == "Open-Meteo"
    issued = datetime.fromisoformat(body["issued_at"])
    assert abs((issued - backdated).total_seconds()) < 1
    assert feed.calls == 2


def test_threshold_and_gdd_ranges(
    client: TestClient,
    db: Session,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    _user, farm, headers = _owned(db, make_user, make_farm, auth_header, "range@agrect.app")
    crop = _olive(db)
    frost = client.put(
        f"/v1/farms/{farm.id}/thresholds",
        headers=headers,
        json={"frost_c": "11", "heat_c": "24"},
    )
    assert frost.status_code == 422
    assert frost.json()["fields"]["frost_c"] == "weather.frost_c_out_of_range"
    assert frost.json()["fields"]["heat_c"] == "weather.heat_c_out_of_range"

    base = client.put(
        f"/v1/farms/{farm.id}/gdd-settings/{crop.id}",
        headers=headers,
        json={"base_c": "21", "method": "average"},
    )
    assert base.status_code == 422
    assert base.json()["fields"]["base_c"] == "gdd.base_out_of_range"

    upper = client.put(
        f"/v1/farms/{farm.id}/gdd-settings/{crop.id}",
        headers=headers,
        json={"base_c": "10", "upper_c": "10", "method": "average"},
    )
    assert upper.status_code == 422
    assert upper.json()["fields"]["upper_c"] == "gdd.upper_not_above_base"

    high = client.put(
        f"/v1/farms/{farm.id}/gdd-settings/{crop.id}",
        headers=headers,
        json={"base_c": "10", "upper_c": "46", "method": "single_sine"},
    )
    assert high.status_code == 422
    assert high.json()["fields"]["upper_c"] == "gdd.upper_out_of_range"

    edges = client.put(
        f"/v1/farms/{farm.id}/thresholds",
        headers=headers,
        json={"frost_c": "-10", "heat_c": "50", "vpd_limit_kpa": "0"},
    )
    assert edges.status_code == 200
    assert edges.json()["frost_c"] == "-10"


def test_gdd_start_date_when_from_omitted(
    client: TestClient,
    db: Session,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
    monkeypatch,
) -> None:
    _user, farm, headers = _owned(db, make_user, make_farm, auth_header, "start@agrect.app")
    crop = _olive(db)
    today = datetime.now(UTC).astimezone(ZONE).date()
    early = today - timedelta(days=4)
    late = today - timedelta(days=2)
    feed = _Feed(
        [
            _point(_local(early, 8), Decimal("14")),
            _point(_local(early, 15), Decimal("30")),
            _point(_local(late, 8), Decimal("14")),
            _point(_local(late, 15), Decimal("30")),
        ]
    )
    monkeypatch.setattr("app.modules.weather.service.fetch_forecast", feed)
    assert client.post(f"/v1/farms/{farm.id}/weather/refresh", headers=headers).status_code == 200
    missing = client.get(
        f"/v1/farms/{farm.id}/weather/degree-days",
        headers=headers,
        params={"crop_id": str(crop.id)},
    )
    assert missing.status_code == 422
    assert missing.json()["code"] == "gdd.start_date_required"

    saved = client.put(
        f"/v1/farms/{farm.id}/gdd-settings/{crop.id}",
        headers=headers,
        json={"base_c": "10", "method": "average", "start_date": late.isoformat()},
    )
    assert saved.status_code == 200
    assert saved.json()["start_date"] == late.isoformat()
    again = client.get(f"/v1/farms/{farm.id}/gdd-settings/{crop.id}", headers=headers)
    assert again.status_code == 200
    assert again.json()["start_date"] == late.isoformat()

    implied = client.get(
        f"/v1/farms/{farm.id}/weather/degree-days",
        headers=headers,
        params={"crop_id": str(crop.id)},
    )
    assert implied.status_code == 200
    body = implied.json()
    assert body["from"] == late.isoformat()
    assert body["setting"]["start_date"] == late.isoformat()
    assert [row["date"] for row in body["days"]] == [late.isoformat()]
    assert Decimal(body["gdd_total"]) == Decimal("12")

    explicit = client.get(
        f"/v1/farms/{farm.id}/weather/degree-days",
        headers=headers,
        params={"crop_id": str(crop.id), "from": early.isoformat()},
    )
    assert explicit.status_code == 200
    assert [row["date"] for row in explicit.json()["days"]] == [
        early.isoformat(),
        late.isoformat(),
    ]
    assert Decimal(explicit.json()["gdd_total"]) == Decimal("24")


def test_gdd_settings_list(
    client: TestClient,
    db: Session,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    _user, farm, headers = _owned(db, make_user, make_farm, auth_header, "list@agrect.app")
    olive = _olive(db)
    apple = Crop(
        code="apple",
        kind=CropKind.perennial,
        sort=2,
        name_fr="Pommier",
        name_ar="تفاح",
        name_en="Apple",
    )
    db.add(apple)
    db.commit()
    db.refresh(apple)
    assert (
        client.put(
            f"/v1/farms/{farm.id}/gdd-settings/{apple.id}",
            headers=headers,
            json={"base_c": "7", "method": "single_sine", "start_date": "2026-11-01"},
        ).status_code
        == 200
    )
    assert (
        client.put(
            f"/v1/farms/{farm.id}/gdd-settings/{olive.id}",
            headers=headers,
            json={"base_c": "10", "upper_c": "30", "method": "average", "start_date": "2026-03-01"},
        ).status_code
        == 200
    )
    listed = client.get(f"/v1/farms/{farm.id}/gdd-settings", headers=headers)
    assert listed.status_code == 200
    rows = listed.json()
    assert [row["code"] for row in rows] == ["olive", "apple"]
    assert rows[0]["name"] == {"fr": "Olivier", "ar": "زيتون", "en": "Olive"}
    assert rows[0]["base_c"] == "10"
    assert rows[0]["upper_c"] == "30"
    assert rows[0]["method"] == "average"
    assert rows[0]["start_date"] == "2026-03-01"
    assert rows[0]["crop_id"] == str(olive.id)
    assert rows[1]["method"] == "single_sine"
    assert rows[1]["start_date"] == "2026-11-01"
    assert rows[1]["upper_c"] is None


def test_radiation_sum_today(
    client: TestClient,
    db: Session,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
    monkeypatch,
) -> None:
    _user, farm, headers = _owned(db, make_user, make_farm, auth_header, "rad@agrect.app")
    now = datetime.now(UTC)
    today = now.astimezone(ZONE).date()
    earlier = now - timedelta(hours=2)
    later = now - timedelta(hours=1)
    feed = _Feed(
        [
            _point(earlier, Decimal("16"), rad=Decimal("100")),
            _point(later, Decimal("18"), rad=Decimal("200")),
            _point(now + timedelta(hours=3), Decimal("20"), rad=Decimal("900")),
        ]
    )
    monkeypatch.setattr("app.modules.weather.service.fetch_forecast", feed)
    assert client.post(f"/v1/farms/{farm.id}/weather/refresh", headers=headers).status_code == 200
    response = client.get(f"/v1/farms/{farm.id}/weather/now", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["rad_sum_source"] == "calculated"
    counted = [
        row.rad_wm2
        for row in feed.rows
        if row.rad_wm2 is not None and row.ts <= now and row.ts.astimezone(ZONE).date() == today
    ]
    if counted:
        assert Decimal(body["rad_sum_jcm2_today"]) == radiation_sum_jcm2(counted)
    else:
        assert body["rad_sum_jcm2_today"] is None
    if len(counted) == 2:
        assert Decimal(body["rad_sum_jcm2_today"]) == Decimal("108.00")


def test_other_users_farm_is_not_found(
    client: TestClient,
    db: Session,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    _owner, farm, _headers = _owned(db, make_user, make_farm, auth_header, "owner@agrect.app")
    stranger = make_user("stranger@agrect.app", "password-stranger")
    headers = auth_header(stranger)
    now = client.get(f"/v1/farms/{farm.id}/weather/now", headers=headers)
    assert now.status_code == 404
    assert now.json() == {"code": "farm.not_found"}
    denied = client.put(
        f"/v1/farms/{farm.id}/thresholds",
        headers=headers,
        json={"frost_c": "0"},
    )
    assert denied.status_code == 404
    assert denied.json() == {"code": "farm.not_found"}
    missing = client.get(
        f"/v1/farms/{uuid.uuid4()}/weather/forecast",
        headers=headers,
    )
    assert missing.status_code == 404
    assert missing.json() == {"code": "farm.not_found"}
