"""Open-Meteo forecast and archive clients.

Hourly rows come from the forecast endpoint (past_days=92, D-048).
Multi-year daily history comes from the archive endpoint (D-059).
Values are parsed with ``Decimal(str(x))`` so floats never reach the database.
"""

import time
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import httpx

from app.core.config import get_settings

_TIMEOUT_S = 15.0
_ARCHIVE_TIMEOUT_S = 30.0
_ATTEMPTS = 3
_RETRY_BACKOFF_S = (0.25, 0.5)
PAST_DAYS = 92
FORECAST_DAYS = 7
ARCHIVE_DAILY = "temperature_2m_max,temperature_2m_min,precipitation_sum,et0_fao_evapotranspiration"
HOURLY_VARS = (
    "temperature_2m,relative_humidity_2m,precipitation,precipitation_probability,"
    "wind_speed_10m,wind_gusts_10m,wind_direction_10m,shortwave_radiation,"
    "et0_fao_evapotranspiration"
)

_HOURLY_FIELDS = (
    ("temperature_2m", "temp_c"),
    ("relative_humidity_2m", "rh_pct"),
    ("precipitation", "rain_mm"),
    ("precipitation_probability", "rain_prob_pct"),
    ("wind_speed_10m", "wind_ms"),
    ("wind_gusts_10m", "gust_ms"),
    ("wind_direction_10m", "wind_dir_deg"),
    ("shortwave_radiation", "rad_wm2"),
    ("et0_fao_evapotranspiration", "et0_mm"),
)

_ARCHIVE_FIELDS = (
    ("temperature_2m_min", "tmin_c"),
    ("temperature_2m_max", "tmax_c"),
    ("precipitation_sum", "rain_mm"),
    ("et0_fao_evapotranspiration", "et0_mm"),
)


class WeatherProviderError(Exception):
    """Open-Meteo could not be fetched or parsed."""


@dataclass(frozen=True, slots=True)
class ArchiveDay:
    day: date
    tmin_c: Decimal | None
    tmax_c: Decimal | None
    rain_mm: Decimal | None
    et0_mm: Decimal | None


@dataclass(frozen=True, slots=True)
class HourlyObservation:
    ts: datetime
    temp_c: Decimal | None
    rh_pct: Decimal | None
    rain_mm: Decimal | None
    rain_prob_pct: Decimal | None
    wind_ms: Decimal | None
    gust_ms: Decimal | None
    wind_dir_deg: Decimal | None
    rad_wm2: Decimal | None
    et0_mm: Decimal | None


def fetch_forecast(
    latitude: Decimal,
    longitude: Decimal,
    *,
    http_client: httpx.Client | None = None,
) -> list[HourlyObservation]:
    """Fetch past 92 days, the current day, and a 7-day forecast.

    Uses a 15 s timeout and 2 retries with backoff. ``http_client`` lets tests
    inject ``httpx.MockTransport``; the real API is not called from tests.
    """
    if http_client is None:
        with httpx.Client(timeout=_TIMEOUT_S) as client:
            return _fetch(client, latitude, longitude)
    return _fetch(http_client, latitude, longitude)


def _fetch(client: httpx.Client, latitude: Decimal, longitude: Decimal) -> list[HourlyObservation]:
    params = {
        "latitude": format(latitude, "f"),
        "longitude": format(longitude, "f"),
        "hourly": HOURLY_VARS,
        "past_days": str(PAST_DAYS),
        "forecast_days": str(FORECAST_DAYS),
        "timezone": "UTC",
        "wind_speed_unit": "ms",
    }
    response = _get_with_retries(client, get_settings().open_meteo_url, params)
    try:
        payload = response.json()
    except ValueError as exc:
        raise WeatherProviderError("open-meteo json") from exc
    return parse_forecast(payload)


def _get_with_retries(client: httpx.Client, url: str, params: dict[str, str]) -> httpx.Response:
    last_error: Exception | None = None
    for attempt in range(_ATTEMPTS):
        try:
            response = client.get(url, params=params)
        except httpx.HTTPError as exc:
            last_error = exc
        else:
            if response.status_code == 429 or response.status_code >= 500:
                last_error = WeatherProviderError(f"status {response.status_code}")
            elif response.is_error:
                raise WeatherProviderError(f"status {response.status_code}") from None
            else:
                return response
        if attempt < _ATTEMPTS - 1:
            time.sleep(_RETRY_BACKOFF_S[attempt])
    raise WeatherProviderError("open-meteo request failed") from last_error


def parse_forecast(payload: object) -> list[HourlyObservation]:
    """Turn an Open-Meteo forecast body into hourly observations."""
    if not isinstance(payload, dict):
        raise WeatherProviderError("open-meteo payload")
    hourly = payload.get("hourly")
    if not isinstance(hourly, dict):
        raise WeatherProviderError("open-meteo hourly")
    times = hourly.get("time")
    if not isinstance(times, list) or not times:
        raise WeatherProviderError("open-meteo time")
    columns: dict[str, list[object]] = {}
    for key, _name in _HOURLY_FIELDS:
        values = hourly.get(key)
        if not isinstance(values, list) or len(values) != len(times):
            raise WeatherProviderError(f"open-meteo {key}")
        columns[key] = values
    observations: list[HourlyObservation] = []
    for index, raw_time in enumerate(times):
        if not isinstance(raw_time, str):
            raise WeatherProviderError("open-meteo time")
        values = {name: _decimal(columns[key][index]) for key, name in _HOURLY_FIELDS}
        observations.append(HourlyObservation(ts=_parse_time(raw_time), **values))
    return observations


def _decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        raise WeatherProviderError("open-meteo value")
    return Decimal(str(value))


def year_chunks(start: date, end: date) -> list[tuple[date, date]]:
    """Split an inclusive span into calendar years, each one year or shorter."""
    if end < start:
        return []
    chunks: list[tuple[date, date]] = []
    cursor = start
    while cursor <= end:
        year_end = date(cursor.year, 12, 31)
        chunk_end = year_end if year_end < end else end
        chunks.append((cursor, chunk_end))
        cursor = chunk_end + timedelta(days=1)
    return chunks


def fetch_archive(
    latitude: Decimal,
    longitude: Decimal,
    start: date,
    end: date,
    timezone: str,
    *,
    http_client: httpx.Client | None = None,
) -> list[ArchiveDay]:
    """Fetch daily archive values for an inclusive farm-local date span.

    ``timezone`` is the farm's IANA zone. Open-Meteo then returns calendar
    dates in that zone. Requests are split so each one covers at most one
    calendar year. Timeout is 30 s, with 2 retries. ``http_client`` lets tests
    inject ``httpx.MockTransport``; the real archive is not called from tests.
    """
    if end < start:
        return []
    if http_client is None:
        with httpx.Client(timeout=_ARCHIVE_TIMEOUT_S) as client:
            return _fetch_archive(client, latitude, longitude, start, end, timezone)
    return _fetch_archive(http_client, latitude, longitude, start, end, timezone)


def _fetch_archive(
    client: httpx.Client,
    latitude: Decimal,
    longitude: Decimal,
    start: date,
    end: date,
    timezone: str,
) -> list[ArchiveDay]:
    days: list[ArchiveDay] = []
    for chunk_start, chunk_end in year_chunks(start, end):
        params = {
            "latitude": format(latitude, "f"),
            "longitude": format(longitude, "f"),
            "start_date": chunk_start.isoformat(),
            "end_date": chunk_end.isoformat(),
            "daily": ARCHIVE_DAILY,
            "timezone": timezone,
        }
        response = _get_with_retries(client, get_settings().open_meteo_archive_url, params)
        try:
            payload = response.json()
        except ValueError as exc:
            raise WeatherProviderError("open-meteo json") from exc
        days.extend(parse_archive(payload))
    return days


def parse_archive(payload: object) -> list[ArchiveDay]:
    """Turn an Open-Meteo archive body into daily rows."""
    if not isinstance(payload, dict):
        raise WeatherProviderError("open-meteo payload")
    daily = payload.get("daily")
    if not isinstance(daily, dict):
        raise WeatherProviderError("open-meteo daily")
    times = daily.get("time")
    if not isinstance(times, list) or not times:
        raise WeatherProviderError("open-meteo time")
    columns: dict[str, list[object]] = {}
    for key, _name in _ARCHIVE_FIELDS:
        values = daily.get(key)
        if not isinstance(values, list) or len(values) != len(times):
            raise WeatherProviderError(f"open-meteo {key}")
        columns[key] = values
    rows: list[ArchiveDay] = []
    for index, raw_day in enumerate(times):
        if not isinstance(raw_day, str):
            raise WeatherProviderError("open-meteo time")
        values = {name: _decimal(columns[key][index]) for key, name in _ARCHIVE_FIELDS}
        rows.append(ArchiveDay(day=_parse_day(raw_day), **values))
    return rows


def _parse_day(value: str) -> date:
    try:
        return date.fromisoformat(value[:10])
    except ValueError as exc:
        raise WeatherProviderError("open-meteo date") from exc


def _parse_time(value: str) -> datetime:
    text = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise WeatherProviderError("open-meteo time") from exc
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
