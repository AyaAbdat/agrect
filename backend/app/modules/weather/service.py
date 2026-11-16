"""Store Open-Meteo hours and derive farm-local daily weather.

Reads refresh the farm when the newest ``issued_at`` is older than 60 minutes
(D-045). A failed fetch keeps the stored rows and marks the response stale.
"""

import hashlib
import json
import logging
import uuid
from collections.abc import Iterable, Sequence
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.events import publish
from app.modules.catalog.models import Crop
from app.modules.catalog.schemas import LocalizedName
from app.modules.farms.models import Farm
from app.modules.farms.service import read_lat_lon
from app.modules.weather.calc import (
    chill_hours,
    count_hours_at_or_above,
    count_hours_at_or_below,
    dewpoint_c,
    gdd_average,
    gdd_single_sine,
    radiation_sum_jcm2,
    vpd_kpa,
)
from app.modules.weather.client import HourlyObservation, WeatherProviderError, fetch_forecast
from app.modules.weather.models import (
    FarmThresholds,
    GddMethod,
    GddSetting,
    WeatherDaily,
    WeatherHourly,
)
from app.modules.weather.schemas import (
    ChillOut,
    DailyOut,
    DailyRowOut,
    DegreeDayPoint,
    DegreeDaysOut,
    ForecastDayOut,
    ForecastHourOut,
    ForecastOut,
    GddSettingBrief,
    GddSettingIn,
    GddSettingListItem,
    GddSettingOut,
    NowOut,
    RefreshOut,
    ThresholdsIn,
    ThresholdsOut,
)

logger = logging.getLogger(__name__)

SOURCE = "estimated"
STALE_AFTER = timedelta(minutes=60)
_UPSERT_CHUNK = 400

_FROST_MIN = Decimal("-10")
_FROST_MAX = Decimal("10")
_HEAT_MIN = Decimal("25")
_HEAT_MAX = Decimal("50")
_VPD_MIN = Decimal("0")
_VPD_MAX = Decimal("10")
_BASE_MIN = Decimal("-5")
_BASE_MAX = Decimal("20")
_UPPER_MAX = Decimal("45")


def refresh(db: Session, farm: Farm) -> RefreshOut:
    """Fetch Open-Meteo and upsert hourly and daily rows for this farm."""
    latitude, longitude = read_lat_lon(db, farm)
    if latitude is None or longitude is None:
        raise AppError("weather.location_required", 422)
    observations = fetch_forecast(latitude, longitude)
    if not observations:
        raise WeatherProviderError("open-meteo returned no hours")
    issued_at = datetime.now(UTC)
    zone = _zone(farm)
    hourly_rows = [_hourly_values(farm.id, obs, issued_at) for obs in _dedupe(observations)]
    _upsert(db, WeatherHourly, hourly_rows, ("farm_id", "ts"))
    touched = {_local_date(row["ts"], zone) for row in hourly_rows}
    days = _rederive(db, farm, zone, issued_at, touched)
    publish(
        "weather.daily_ready",
        {
            "db": db,
            "farm_id": farm.id,
            "from_date": min(touched) if touched else None,
        },
    )
    db.commit()
    return RefreshOut(issued_at=issued_at, hours=len(hourly_rows), days=days)


def ensure_fresh(db: Session, farm: Farm) -> bool:
    """Refresh when data is missing or older than 60 minutes.

    Returns True when the stored data is stale because the provider failed.
    """
    latest = _latest_issued_at(db, farm.id)
    now = datetime.now(UTC)
    if latest is not None and now - latest <= STALE_AFTER:
        return False
    try:
        refresh(db, farm)
    except WeatherProviderError:
        logger.warning("open-meteo refresh failed for farm %s", farm.id)
        if _latest_issued_at(db, farm.id) is None:
            raise AppError("weather.unavailable", 503) from None
        return True
    return False


def read_now(db: Session, farm: Farm) -> NowOut:
    stale = ensure_fresh(db, farm)
    now = datetime.now(UTC)
    zone = _zone(farm)
    hour = db.scalars(
        select(WeatherHourly)
        .where(WeatherHourly.farm_id == farm.id, WeatherHourly.ts <= now)
        .order_by(WeatherHourly.ts.desc())
        .limit(1)
    ).first()
    if hour is None:
        raise AppError("weather.not_found", 404)
    today = now.astimezone(zone).date()
    start = datetime.combine(today, time.min, tzinfo=zone)
    today_hours = db.scalars(
        select(WeatherHourly).where(
            WeatherHourly.farm_id == farm.id,
            WeatherHourly.ts >= start,
            WeatherHourly.ts <= now,
        )
    ).all()
    rad_values = [row.rad_wm2 for row in today_hours if row.rad_wm2 is not None]
    return NowOut(
        temp_c=hour.temp_c,
        rh_pct=hour.rh_pct,
        wind_ms=hour.wind_ms,
        gust_ms=hour.gust_ms,
        wind_dir_deg=hour.wind_dir_deg,
        rad_wm2=hour.rad_wm2,
        dewpoint_c=hour.dewpoint_c,
        vpd_kpa=hour.vpd_kpa,
        rain_mm=_sum_decimal(row.rain_mm for row in today_hours),
        et0_mm=_sum_decimal(row.et0_mm for row in today_hours),
        rad_sum_jcm2_today=radiation_sum_jcm2(rad_values) if rad_values else None,
        ts=hour.ts,
        issued_at=_latest_issued_at(db, farm.id),
        stale=stale,
    )


def read_forecast(db: Session, farm: Farm) -> ForecastOut:
    stale = ensure_fresh(db, farm)
    now = datetime.now(UTC)
    zone = _zone(farm)
    today = now.astimezone(zone).date()
    end = today + timedelta(days=6)
    hourly = db.scalars(
        select(WeatherHourly)
        .where(WeatherHourly.farm_id == farm.id, WeatherHourly.ts > now)
        .order_by(WeatherHourly.ts)
        .limit(48)
    ).all()
    daily = db.scalars(
        select(WeatherDaily)
        .where(
            WeatherDaily.farm_id == farm.id,
            WeatherDaily.date >= today,
            WeatherDaily.date <= end,
        )
        .order_by(WeatherDaily.date)
    ).all()
    rain_prob = _rain_prob_max(db, farm, zone, today, end)
    return ForecastOut(
        issued_at=_latest_issued_at(db, farm.id),
        stale=stale,
        hourly=[_forecast_hour(row) for row in hourly],
        daily=[_forecast_day(row, rain_prob.get(row.date)) for row in daily],
    )


def read_daily(
    db: Session,
    farm: Farm,
    *,
    from_date: date | None,
    to_date: date | None,
) -> DailyOut:
    stale = ensure_fresh(db, farm)
    today = datetime.now(UTC).astimezone(_zone(farm)).date()
    stmt = select(WeatherDaily).where(
        WeatherDaily.farm_id == farm.id,
        WeatherDaily.date < today,
    )
    if from_date is not None:
        stmt = stmt.where(WeatherDaily.date >= from_date)
    if to_date is not None:
        stmt = stmt.where(WeatherDaily.date <= to_date)
    rows = db.scalars(stmt.order_by(WeatherDaily.date)).all()
    return DailyOut(
        issued_at=_latest_issued_at(db, farm.id),
        stale=stale,
        days=[_daily_out(row) for row in rows],
    )


def read_degree_days(
    db: Session,
    farm: Farm,
    crop_id: uuid.UUID,
    from_date: date | None,
) -> DegreeDaysOut:
    _require_crop(db, crop_id)
    saved = _gdd_row(db, farm.id, crop_id)
    if from_date is None:
        if saved is None or saved.start_date is None:
            raise AppError("gdd.start_date_required", 422)
        from_date = saved.start_date
    stale = ensure_fresh(db, farm)
    setting = _gdd_row(db, farm.id, crop_id)
    rows = list(
        db.scalars(
            select(WeatherDaily)
            .where(WeatherDaily.farm_id == farm.id, WeatherDaily.date >= from_date)
            .order_by(WeatherDaily.date)
        ).all()
    )
    data_from = db.scalar(
        select(func.min(WeatherDaily.date)).where(WeatherDaily.farm_id == farm.id)
    )
    thresholds = db.get(FarmThresholds, farm.id)
    marker = None if thresholds is None else thresholds.chill_season_start
    season = None
    if marker is not None:
        season = season_start(datetime.now(UTC).astimezone(_zone(farm)).date(), marker)
    points: list[DegreeDayPoint] = []
    cumulative: Decimal | None = None
    any_gdd = False
    brief: GddSettingBrief | None = None
    if setting is None:
        points = [
            DegreeDayPoint(date=row.date, gdd=None, gdd_cum=None, is_forecast=row.is_forecast)
            for row in rows
        ]
        label = "not_enough_data"
        gdd_total = None
    else:
        brief = GddSettingBrief(
            base_c=setting.base_c,
            upper_c=setting.upper_c,
            method=setting.method,
            start_date=setting.start_date,
        )
        for row in rows:
            gdd = _gdd_for_row(row, setting)
            if gdd is None:
                points.append(
                    DegreeDayPoint(
                        date=row.date,
                        gdd=None,
                        gdd_cum=cumulative,
                        is_forecast=row.is_forecast,
                    )
                )
                continue
            cumulative = gdd if cumulative is None else cumulative + gdd
            any_gdd = True
            points.append(
                DegreeDayPoint(
                    date=row.date,
                    gdd=gdd,
                    gdd_cum=cumulative,
                    is_forecast=row.is_forecast,
                )
            )
        gdd_total = cumulative
        label = "calculated" if any_gdd else "not_enough_data"
    return DegreeDaysOut(
        setting=brief,
        from_date=from_date,
        data_from=data_from,
        days=points,
        gdd_total=gdd_total,
        chill=ChillOut(season_start=season, hours_total=_sum_int(row.chill_h for row in rows)),
        frost_h_total=_sum_int(row.frost_h for row in rows),
        heat_h_total=_sum_int(row.heat_h for row in rows),
        label=label,
        issued_at=_latest_issued_at(db, farm.id),
        stale=stale,
    )


def read_thresholds(db: Session, farm: Farm) -> ThresholdsOut:
    row = db.get(FarmThresholds, farm.id)
    if row is None:
        return ThresholdsOut(
            frost_c=None,
            heat_c=None,
            vpd_limit_kpa=None,
            chill_season_start=None,
        )
    return _thresholds_out(row)


def write_thresholds(db: Session, farm: Farm, body: ThresholdsIn) -> ThresholdsOut:
    _validate_thresholds(body)
    row = db.get(FarmThresholds, farm.id)
    if row is None:
        row = FarmThresholds(farm_id=farm.id)
        db.add(row)
    row.frost_c = body.frost_c
    row.heat_c = body.heat_c
    row.vpd_limit_kpa = body.vpd_limit_kpa
    row.chill_season_start = body.chill_season_start
    db.flush()
    _rederive(db, farm, _zone(farm), datetime.now(UTC), None)
    publish("weather.daily_ready", {"db": db, "farm_id": farm.id, "from_date": None})
    db.commit()
    db.refresh(row)
    return _thresholds_out(row)


def read_gdd_settings(db: Session, farm: Farm) -> list[GddSettingListItem]:
    rows = db.execute(
        select(GddSetting, Crop)
        .join(Crop, Crop.id == GddSetting.crop_id)
        .where(GddSetting.farm_id == farm.id)
        .order_by(Crop.sort, Crop.code)
    ).all()
    return [
        GddSettingListItem(
            crop_id=crop.id,
            code=crop.code,
            name=LocalizedName(fr=crop.name_fr, ar=crop.name_ar, en=crop.name_en),
            base_c=setting.base_c,
            upper_c=setting.upper_c,
            method=setting.method,
            start_date=setting.start_date,
        )
        for setting, crop in rows
    ]


def read_gdd_setting(db: Session, farm: Farm, crop_id: uuid.UUID) -> GddSettingOut:
    _require_crop(db, crop_id)
    row = _gdd_row(db, farm.id, crop_id)
    if row is None:
        return GddSettingOut(
            crop_id=crop_id, base_c=None, upper_c=None, method=None, start_date=None
        )
    return GddSettingOut(
        crop_id=crop_id,
        base_c=row.base_c,
        upper_c=row.upper_c,
        method=row.method,
        start_date=row.start_date,
    )


def write_gdd_setting(
    db: Session,
    farm: Farm,
    crop_id: uuid.UUID,
    body: GddSettingIn,
) -> GddSettingOut:
    _require_crop(db, crop_id)
    _validate_gdd(body)
    row = _gdd_row(db, farm.id, crop_id)
    if row is None:
        row = GddSetting(
            farm_id=farm.id,
            crop_id=crop_id,
            base_c=body.base_c,
            upper_c=body.upper_c,
            method=body.method,
            start_date=body.start_date,
        )
        db.add(row)
    else:
        row.base_c = body.base_c
        row.upper_c = body.upper_c
        row.method = body.method
        row.start_date = body.start_date
    db.commit()
    db.refresh(row)
    return GddSettingOut(
        crop_id=crop_id,
        base_c=row.base_c,
        upper_c=row.upper_c,
        method=row.method,
        start_date=row.start_date,
    )


def season_start(today: date, marker: date) -> date:
    """Most recent month-day of ``marker`` on or before ``today``.

    The stored year is ignored. 29 February falls back to 28 February when the
    target year is not a leap year.
    """

    def on_year(year: int) -> date:
        try:
            return date(year, marker.month, marker.day)
        except ValueError:
            return date(year, 2, 28)

    this_year = on_year(today.year)
    if this_year <= today:
        return this_year
    return on_year(today.year - 1)


def _validate_thresholds(body: ThresholdsIn) -> None:
    fields: dict[str, str] = {}
    if body.frost_c is not None and _outside(body.frost_c, _FROST_MIN, _FROST_MAX):
        fields["frost_c"] = "weather.frost_c_out_of_range"
    if body.heat_c is not None and _outside(body.heat_c, _HEAT_MIN, _HEAT_MAX):
        fields["heat_c"] = "weather.heat_c_out_of_range"
    if body.vpd_limit_kpa is not None and _outside(body.vpd_limit_kpa, _VPD_MIN, _VPD_MAX):
        fields["vpd_limit_kpa"] = "weather.vpd_limit_kpa_out_of_range"
    if fields:
        raise AppError("validation_error", 422, fields)


def _validate_gdd(body: GddSettingIn) -> None:
    fields: dict[str, str] = {}
    if _outside(body.base_c, _BASE_MIN, _BASE_MAX):
        fields["base_c"] = "gdd.base_out_of_range"
    if body.upper_c is not None and body.upper_c <= body.base_c:
        fields["upper_c"] = "gdd.upper_not_above_base"
    elif body.upper_c is not None and body.upper_c > _UPPER_MAX:
        fields["upper_c"] = "gdd.upper_out_of_range"
    if fields:
        raise AppError("validation_error", 422, fields)


def _outside(value: Decimal, low: Decimal, high: Decimal) -> bool:
    return value < low or value > high


def _require_crop(db: Session, crop_id: uuid.UUID) -> Crop:
    crop = db.get(Crop, crop_id)
    if crop is None:
        raise AppError("catalog.crop_not_found", 404)
    return crop


def _gdd_row(db: Session, farm_id: uuid.UUID, crop_id: uuid.UUID) -> GddSetting | None:
    return db.scalar(
        select(GddSetting).where(GddSetting.farm_id == farm_id, GddSetting.crop_id == crop_id)
    )


def _gdd_for_row(row: WeatherDaily, setting: GddSetting) -> Decimal | None:
    if row.tmin_c is None or row.tmax_c is None:
        return None
    if setting.method == GddMethod.single_sine:
        return gdd_single_sine(row.tmax_c, row.tmin_c, setting.base_c, setting.upper_c)
    return gdd_average(row.tmax_c, row.tmin_c, setting.base_c, setting.upper_c)


def _zone(farm: Farm) -> ZoneInfo:
    return ZoneInfo(farm.timezone)


def _local_date(ts: datetime, zone: ZoneInfo) -> date:
    aware = ts if ts.tzinfo is not None else ts.replace(tzinfo=UTC)
    return aware.astimezone(zone).date()


def _dedupe(observations: Sequence[HourlyObservation]) -> list[HourlyObservation]:
    by_ts: dict[datetime, HourlyObservation] = {}
    for obs in observations:
        stamp = obs.ts if obs.ts.tzinfo is not None else obs.ts.replace(tzinfo=UTC)
        by_ts[stamp.astimezone(UTC)] = obs
    return [by_ts[stamp] for stamp in sorted(by_ts)]


def _psychrometric(
    temp_c: Decimal | None,
    rh_pct: Decimal | None,
) -> tuple[Decimal | None, Decimal | None]:
    if temp_c is None or rh_pct is None or rh_pct <= 0 or rh_pct > 100:
        return None, None
    try:
        return dewpoint_c(temp_c, rh_pct), vpd_kpa(temp_c, rh_pct)
    except (InvalidOperation, ZeroDivisionError):
        return None, None


def _hourly_values(
    farm_id: uuid.UUID,
    obs: HourlyObservation,
    issued_at: datetime,
) -> dict[str, object]:
    dewpoint, vpd = _psychrometric(obs.temp_c, obs.rh_pct)
    return {
        "farm_id": farm_id,
        "ts": obs.ts,
        "temp_c": obs.temp_c,
        "rh_pct": obs.rh_pct,
        "rain_mm": obs.rain_mm,
        "rain_prob_pct": obs.rain_prob_pct,
        "wind_ms": obs.wind_ms,
        "gust_ms": obs.gust_ms,
        "wind_dir_deg": obs.wind_dir_deg,
        "rad_wm2": obs.rad_wm2,
        "et0_mm": obs.et0_mm,
        "dewpoint_c": dewpoint,
        "vpd_kpa": vpd,
        "is_forecast": obs.ts > issued_at,
        "source": SOURCE,
        "issued_at": issued_at,
    }


def _rederive(
    db: Session,
    farm: Farm,
    zone: ZoneInfo,
    now: datetime,
    only_dates: set[date] | None,
) -> int:
    hours = list(
        db.scalars(
            select(WeatherHourly).where(WeatherHourly.farm_id == farm.id).order_by(WeatherHourly.ts)
        ).all()
    )
    grouped: dict[date, list[WeatherHourly]] = {}
    for hour in hours:
        day = _local_date(hour.ts, zone)
        if only_dates is not None and day not in only_dates:
            continue
        grouped.setdefault(day, []).append(hour)
    if not grouped:
        return 0
    thresholds = db.get(FarmThresholds, farm.id)
    today = now.astimezone(zone).date()
    marker = None if thresholds is None else thresholds.chill_season_start
    season = None if marker is None else season_start(today, marker)
    rows = [
        _daily_values(farm.id, day, day_hours, thresholds, today, season)
        for day, day_hours in sorted(grouped.items())
    ]
    _upsert(db, WeatherDaily, rows, ("farm_id", "date"))
    return len(rows)


def _daily_values(
    farm_id: uuid.UUID,
    day: date,
    day_hours: Sequence[WeatherHourly],
    thresholds: FarmThresholds | None,
    today: date,
    season: date | None,
) -> dict[str, object]:
    temps = [hour.temp_c for hour in day_hours if hour.temp_c is not None]
    rh_values = [hour.rh_pct for hour in day_hours if hour.rh_pct is not None]
    rains = [hour.rain_mm for hour in day_hours if hour.rain_mm is not None]
    et0_values = [hour.et0_mm for hour in day_hours if hour.et0_mm is not None]
    vpds = [hour.vpd_kpa for hour in day_hours if hour.vpd_kpa is not None]
    frost_c = None if thresholds is None else thresholds.frost_c
    heat_c = None if thresholds is None else thresholds.heat_c
    frost_h = None if frost_c is None else count_hours_at_or_below(temps, frost_c)
    heat_h = None if heat_c is None else count_hours_at_or_above(temps, heat_c)
    chill_h = chill_hours(temps) if season is not None and day >= season else None
    is_forecast = day >= today
    payload = {
        "date": day.isoformat(),
        "frost_c": frost_c,
        "heat_c": heat_c,
        "chill_active": chill_h is not None,
        "is_forecast": is_forecast,
        "hours": [
            {
                "ts": hour.ts.isoformat(),
                "temp_c": hour.temp_c,
                "rh_pct": hour.rh_pct,
                "rain_mm": hour.rain_mm,
                "et0_mm": hour.et0_mm,
                "vpd_kpa": hour.vpd_kpa,
            }
            for hour in day_hours
        ],
    }
    return {
        "farm_id": farm_id,
        "date": day,
        "tmin_c": min(temps) if temps else None,
        "tmax_c": max(temps) if temps else None,
        "tmean_c": sum(temps, Decimal(0)) / Decimal(len(temps)) if temps else None,
        "rh_min": min(rh_values) if rh_values else None,
        "rh_max": max(rh_values) if rh_values else None,
        "rain_mm": sum(rains, Decimal(0)) if rains else None,
        "et0_mm": sum(et0_values, Decimal(0)) if et0_values else None,
        "vpd_max_kpa": max(vpds) if vpds else None,
        "frost_h": frost_h,
        "heat_h": heat_h,
        "chill_h": chill_h,
        "hours_count": len(day_hours),
        "is_forecast": is_forecast,
        "source": SOURCE,
        "inputs_hash": _inputs_hash(payload),
    }


def _upsert(
    db: Session,
    model: type[WeatherHourly] | type[WeatherDaily],
    rows: list[dict[str, object]],
    pk: tuple[str, ...],
) -> None:
    if not rows:
        return
    table = model.__table__
    for start in range(0, len(rows), _UPSERT_CHUNK):
        chunk = rows[start : start + _UPSERT_CHUNK]
        stmt = insert(model).values(chunk)
        excluded = stmt.excluded
        stmt = stmt.on_conflict_do_update(
            index_elements=[table.c[name] for name in pk],
            set_={name: getattr(excluded, name) for name in chunk[0] if name not in pk},
        )
        db.execute(stmt)


def _latest_issued_at(db: Session, farm_id: uuid.UUID) -> datetime | None:
    return db.scalar(
        select(func.max(WeatherHourly.issued_at)).where(WeatherHourly.farm_id == farm_id)
    )


def _rain_prob_max(
    db: Session,
    farm: Farm,
    zone: ZoneInfo,
    start: date,
    end: date,
) -> dict[date, Decimal]:
    start_utc = datetime.combine(start, time.min, tzinfo=zone)
    end_utc = datetime.combine(end + timedelta(days=1), time.min, tzinfo=zone)
    hours = db.scalars(
        select(WeatherHourly).where(
            WeatherHourly.farm_id == farm.id,
            WeatherHourly.ts >= start_utc,
            WeatherHourly.ts < end_utc,
        )
    ).all()
    grouped: dict[date, list[Decimal]] = {}
    for hour in hours:
        if hour.rain_prob_pct is None:
            continue
        grouped.setdefault(_local_date(hour.ts, zone), []).append(hour.rain_prob_pct)
    return {day: max(values) for day, values in grouped.items()}


def _forecast_hour(row: WeatherHourly) -> ForecastHourOut:
    return ForecastHourOut(
        ts=row.ts,
        temp_c=row.temp_c,
        rh_pct=row.rh_pct,
        rain_mm=row.rain_mm,
        rain_prob_pct=row.rain_prob_pct,
        wind_ms=row.wind_ms,
        gust_ms=row.gust_ms,
        wind_dir_deg=row.wind_dir_deg,
        rad_wm2=row.rad_wm2,
        et0_mm=row.et0_mm,
        dewpoint_c=row.dewpoint_c,
        vpd_kpa=row.vpd_kpa,
        is_forecast=row.is_forecast,
        source=row.source,
    )


def _forecast_day(row: WeatherDaily, rain_prob_pct: Decimal | None) -> ForecastDayOut:
    return ForecastDayOut(
        date=row.date,
        tmin_c=row.tmin_c,
        tmax_c=row.tmax_c,
        rain_mm=row.rain_mm,
        rain_prob_pct=rain_prob_pct,
        et0_mm=row.et0_mm,
        frost_h=row.frost_h,
        heat_h=row.heat_h,
        is_forecast=row.is_forecast,
        source=row.source,
    )


def _daily_out(row: WeatherDaily) -> DailyRowOut:
    return DailyRowOut(
        date=row.date,
        tmin_c=row.tmin_c,
        tmax_c=row.tmax_c,
        tmean_c=row.tmean_c,
        rh_min=row.rh_min,
        rh_max=row.rh_max,
        rain_mm=row.rain_mm,
        et0_mm=row.et0_mm,
        vpd_max_kpa=row.vpd_max_kpa,
        frost_h=row.frost_h,
        heat_h=row.heat_h,
        chill_h=row.chill_h,
        hours_count=row.hours_count,
        is_forecast=row.is_forecast,
        source=row.source,
    )


def _thresholds_out(row: FarmThresholds) -> ThresholdsOut:
    return ThresholdsOut(
        frost_c=row.frost_c,
        heat_c=row.heat_c,
        vpd_limit_kpa=row.vpd_limit_kpa,
        chill_season_start=row.chill_season_start,
    )


def _sum_decimal(values: Iterable[Decimal | None]) -> Decimal | None:
    present = [value for value in values if value is not None]
    if not present:
        return None
    return sum(present, Decimal(0))


def _sum_int(values: Iterable[int | None]) -> int | None:
    present = [value for value in values if value is not None]
    if not present:
        return None
    return sum(present)


def _jsonable(value: object) -> object:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    return value


def _inputs_hash(payload: dict[str, object]) -> str:
    encoded = json.dumps(_jsonable(payload), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
