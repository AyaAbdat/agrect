import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from app.modules.weather.client import (
    FORECAST_DAYS,
    HOURLY_VARS,
    PAST_DAYS,
    WeatherProviderError,
    fetch_forecast,
)

_FIXTURE = Path(__file__).parent / "fixtures" / "open_meteo_forecast.json"


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
