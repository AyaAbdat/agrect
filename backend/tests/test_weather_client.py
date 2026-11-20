import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from app.modules.weather.client import (
    ARCHIVE_DAILY,
    FORECAST_DAYS,
    HOURLY_VARS,
    PAST_DAYS,
    WeatherProviderError,
    fetch_archive,
    fetch_forecast,
)

_FIXTURE = Path(__file__).parent / "fixtures" / "open_meteo_forecast.json"
_ARCHIVE_FIXTURE = Path(__file__).parent / "fixtures" / "open_meteo_archive.json"


def _payload() -> dict[str, object]:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


def test_parse_forecast_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["past_days"] = request.url.params["past_days"]
        seen["forecast_days"] = request.url.params["forecast_days"]
        seen["timezone"] = request.url.params["timezone"]
        seen["wind_speed_unit"] = request.url.params["wind_speed_unit"]
        seen["hourly"] = request.url.params["hourly"]
        seen["latitude"] = request.url.params["latitude"]
        seen["longitude"] = request.url.params["longitude"]
        return httpx.Response(200, json=_payload())

    monkeypatch.setattr("app.modules.weather.client.time.sleep", lambda _seconds: None)
    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        rows = fetch_forecast(Decimal("36.5"), Decimal("3.25"), http_client=http_client)

    assert seen["path"] == "/v1/forecast"
    assert seen["past_days"] == str(PAST_DAYS)
    assert seen["forecast_days"] == str(FORECAST_DAYS)
    assert seen["timezone"] == "UTC"
    assert seen["wind_speed_unit"] == "ms"
    assert seen["hourly"] == HOURLY_VARS
    assert seen["latitude"] == "36.5"
    assert seen["longitude"] == "3.25"
    assert len(rows) == 72
    assert rows[0].ts == datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    assert rows[0].temp_c == Decimal("10.5")
    assert rows[1].temp_c is None
    assert rows[3].rain_mm == Decimal("1.2")
    assert rows[24].rh_pct is None
    assert rows[48].temp_c == Decimal("5.25")
    assert rows[48].rain_prob_pct == Decimal("80")
    assert rows[0].wind_ms == Decimal("3.5")
    assert rows[0].et0_mm == Decimal("0.01")
    assert all(row.temp_c is None or type(row.temp_c) is Decimal for row in rows)
    assert all(row.ts.tzinfo is not None for row in rows)


def test_retries_then_parses(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(503)
        return httpx.Response(200, json=_payload())

    monkeypatch.setattr("app.modules.weather.client.time.sleep", lambda _seconds: None)
    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        rows = fetch_forecast(Decimal("36.5"), Decimal("3.25"), http_client=http_client)
    assert calls["n"] == 2
    assert len(rows) == 72


def _archive_payload() -> dict[str, object]:
    return json.loads(_ARCHIVE_FIXTURE.read_text(encoding="utf-8"))


def test_parse_archive_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["start_date"] = request.url.params["start_date"]
        seen["end_date"] = request.url.params["end_date"]
        seen["daily"] = request.url.params["daily"]
        seen["timezone"] = request.url.params["timezone"]
        seen["latitude"] = request.url.params["latitude"]
        seen["longitude"] = request.url.params["longitude"]
        return httpx.Response(200, json=_archive_payload())

    monkeypatch.setattr("app.modules.weather.client.time.sleep", lambda _seconds: None)
    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        rows = fetch_archive(
            Decimal("36.5"),
            Decimal("3.25"),
            date(2020, 1, 1),
            date(2020, 1, 3),
            "Africa/Algiers",
            http_client=http_client,
        )

    assert seen["path"] == "/v1/archive"
    assert seen["start_date"] == "2020-01-01"
    assert seen["end_date"] == "2020-01-03"
    assert seen["daily"] == ARCHIVE_DAILY
    assert seen["timezone"] == "Africa/Algiers"
    assert seen["latitude"] == "36.5"
    assert seen["longitude"] == "3.25"
    assert len(rows) == 3
    assert rows[0].day == date(2020, 1, 1)
    assert rows[0].tmax_c == Decimal("18.5")
    assert rows[0].tmin_c == Decimal("4.5")
    assert rows[1].rain_mm == Decimal("1.25")
    assert rows[1].et0_mm == Decimal("2.0")
    assert rows[2].tmax_c is None
    assert rows[2].et0_mm is None
    assert rows[2].tmin_c == Decimal("3.0")
    assert all(
        value is None or type(value) is Decimal
        for row in rows
        for value in (row.tmin_c, row.tmax_c, row.rain_mm, row.et0_mm)
    )


def test_archive_splits_two_year_range(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.url.params["start_date"], request.url.params["end_date"]))
        start = date.fromisoformat(request.url.params["start_date"])
        return httpx.Response(
            200,
            json={
                "daily": {
                    "time": [start.isoformat()],
                    "temperature_2m_max": [10.0],
                    "temperature_2m_min": [1.0],
                    "precipitation_sum": [0.0],
                    "et0_fao_evapotranspiration": [1.0],
                }
            },
        )

    monkeypatch.setattr("app.modules.weather.client.time.sleep", lambda _seconds: None)
    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        rows = fetch_archive(
            Decimal("36.5"),
            Decimal("3.25"),
            date(2020, 1, 1),
            date(2021, 12, 31),
            "Africa/Algiers",
            http_client=http_client,
        )

    assert calls == [("2020-01-01", "2020-12-31"), ("2021-01-01", "2021-12-31")]
    assert len(rows) == 2
    assert rows[0].day == date(2020, 1, 1)
    assert rows[1].day == date(2021, 1, 1)


def test_archive_retries_then_parses(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(503)
        return httpx.Response(200, json=_archive_payload())

    monkeypatch.setattr("app.modules.weather.client.time.sleep", lambda _seconds: None)
    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        rows = fetch_archive(
            Decimal("36.5"),
            Decimal("3.25"),
            date(2020, 1, 1),
            date(2020, 1, 3),
            "Africa/Algiers",
            http_client=http_client,
        )
    assert calls["n"] == 2
    assert len(rows) == 3


def test_client_error_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(400)

    monkeypatch.setattr("app.modules.weather.client.time.sleep", lambda _seconds: None)
    with httpx.Client(transport=httpx.MockTransport(handler)) as http_client:
        with pytest.raises(WeatherProviderError):
            fetch_forecast(Decimal("36.5"), Decimal("3.25"), http_client=http_client)
    assert calls["n"] == 1
