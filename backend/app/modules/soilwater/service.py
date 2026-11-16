"""Save soil and irrigation settings, log irrigation, and keep the daily water balance."""

import hashlib
import json
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.events import publish, subscribe
from app.modules.auth.models import AppUser
from app.modules.catalog.models import SoilTextureClass
from app.modules.catalog.schemas import LocalizedName
from app.modules.farms.models import Farm
from app.modules.registry.models import Block, IrrigationLayout, RecordVersion, Valve
from app.modules.soilwater import calc
from app.modules.soilwater.models import (
    InfiltrationSource,
    IrrigationEvent,
    IrrigationSettings,
    IrrigationSource,
    SoilCheck,
    SoilFeel,
    SoilProfile,
    TextureMode,
    WaterBalanceDaily,
    WbStatus,
)
from app.modules.soilwater.schemas import (
    BalancePeriod,
    BlockIrrigationTodayOut,
    DoseOut,
    FarmIrrigationTodayOut,
    InfiltrationLabel,
    IrrigationEventIn,
    IrrigationEventOut,
    IrrigationEventPatch,
    IrrigationEventsOut,
    IrrigationPreviewIn,
    IrrigationPreviewOut,
    IrrigationSettingsOut,
    IrrigationSettingsPut,
    IrrigationTodayOut,
    IrrigationTotalsOut,
    SoilCheckIn,
    SoilCheckOut,
    SoilCheckPreviewOut,
    SoilLabel,
    SoilOut,
    SoilPut,
    SoilSources,
    TextureClassOut,
    WaterBalanceOut,
    WaterBalanceRowOut,
)
from app.modules.weather.models import WeatherDaily

_SOIL_ENTITY = "soil_profile"
_SETTINGS_ENTITY = "irrigation_settings"

_SOIL_FIELDS = (
    "texture_mode",
    "texture_class_id",
    "sand_pct",
    "silt_pct",
    "clay_pct",
    "theta_fc",
    "theta_wp",
    "root_depth_m",
    "dry_down_pct",
    "full_on",
    "organic_matter_pct",
    "compaction",
    "infiltration_mm_h",
    "infiltration_source",
)
_SETTINGS_FIELDS = ("efficiency", "kc", "kc_source")

_ROOT_MIN = Decimal("0.1")
_ROOT_MAX = Decimal("3")
_DRY_MIN = Decimal("10")
_DRY_MAX = Decimal("90")
_KC_MIN = Decimal("0.1")
_KC_MAX = Decimal("1.5")


def _clean_reason(reason: str | None) -> str | None:
    if reason is None:
        return None
    stripped = reason.strip()
    if not stripped:
        return None
    return stripped


def _require_if_match(version: int, if_match: str | None) -> None:
    if if_match is None or if_match.strip() == "":
        raise AppError("conflict.version_required", 428)
    token = if_match.strip()
    if len(token) >= 2 and token[0] == '"' and token[-1] == '"':
        token = token[1:-1]
    try:
        presented = int(token)
    except ValueError:
        raise AppError("conflict.version", 409) from None
    if presented != version:
        raise AppError("conflict.version", 409)


def _values(row: object, fields: tuple[str, ...]) -> dict[str, object]:
    return {field: getattr(row, field) for field in fields}


def _changed(before: dict[str, object], row: object, fields: tuple[str, ...]) -> list[str]:
    return [field for field in fields if getattr(row, field) != before[field]]


def _add_history(
    db: Session,
    row: SoilProfile | IrrigationSettings,
    user: AppUser,
    entity_type: str,
    changed: list[str],
    reason: str | None,
) -> None:
    db.add(
        RecordVersion(
            farm_id=row.farm_id,
            entity_type=entity_type,
            entity_id=row.id,
            version=row.version,
            changed_fields=changed,
            reason=reason,
            user_id=user.id,
            changed_at=datetime.now(UTC),
        )
    )


def _soil_row(db: Session, block: Block) -> SoilProfile | None:
    return db.scalar(
        select(SoilProfile).where(
            SoilProfile.block_id == block.id,
            SoilProfile.farm_id == block.farm_id,
        )
    )


def _settings_row(db: Session, block: Block) -> IrrigationSettings | None:
    return db.scalar(
        select(IrrigationSettings).where(
            IrrigationSettings.block_id == block.id,
            IrrigationSettings.farm_id == block.farm_id,
        )
    )


def _texture(db: Session, texture_class_id: uuid.UUID | None) -> SoilTextureClass | None:
    if texture_class_id is None:
        return None
    return db.get(SoilTextureClass, texture_class_id)


def _soil_errors(db: Session, body: SoilPut) -> dict[str, str]:
    errors: dict[str, str] = {}
    if body.root_depth_m is not None and (
        body.root_depth_m < _ROOT_MIN or body.root_depth_m > _ROOT_MAX
    ):
        errors["root_depth_m"] = "soil.root_depth_out_of_range"
    if body.dry_down_pct is not None and (
        body.dry_down_pct < _DRY_MIN or body.dry_down_pct > _DRY_MAX
    ):
        errors["dry_down_pct"] = "soil.dry_down_out_of_range"
    if body.texture_mode == TextureMode.percent:
        sand, silt, clay = body.sand_pct, body.silt_pct, body.clay_pct
        if sand is None or silt is None or clay is None or sand + silt + clay != Decimal(100):
            errors["sand_pct"] = "soil.percent_sum_invalid"
    if body.texture_class_id is not None and _texture(db, body.texture_class_id) is None:
        errors["texture_class_id"] = "catalog.soil_texture_not_found"
    return errors


def _settings_errors(body: IrrigationSettingsPut) -> dict[str, str]:
    errors: dict[str, str] = {}
    if body.efficiency is not None and (body.efficiency <= 0 or body.efficiency > 1):
        errors["efficiency"] = "irrigation.efficiency_out_of_range"
    if body.kc is not None and (body.kc < _KC_MIN or body.kc > _KC_MAX):
        errors["kc"] = "irrigation.kc_out_of_range"
    return errors


def _reason_error(exists: bool, reason: str | None) -> dict[str, str]:
    if exists and _clean_reason(reason) is None:
        return {"reason": "record.reason_required"}
    return {}


def _apply_soil(row: SoilProfile, body: SoilPut, texture: SoilTextureClass | None) -> None:
    row.texture_mode = body.texture_mode
    row.texture_class_id = body.texture_class_id
    row.sand_pct = body.sand_pct
    row.silt_pct = body.silt_pct
    row.clay_pct = body.clay_pct
    row.root_depth_m = body.root_depth_m
    row.dry_down_pct = body.dry_down_pct
    row.full_on = body.full_on
    row.organic_matter_pct = body.organic_matter_pct
    row.compaction = body.compaction
    row.infiltration_mm_h = body.infiltration_mm_h
    row.infiltration_source = body.infiltration_source
    if body.texture_mode == TextureMode.percent or texture is None:
        row.theta_fc = None
        row.theta_wp = None
    else:
        row.theta_fc = texture.theta_fc
        row.theta_wp = texture.theta_wp
    row.updated_at = datetime.now(UTC)


def _apply_settings(row: IrrigationSettings, body: IrrigationSettingsPut) -> None:
    row.efficiency = body.efficiency
    row.kc = body.kc
    row.kc_source = body.kc_source
    row.updated_at = datetime.now(UTC)


def _water_store(
    row: SoilProfile,
) -> tuple[Decimal | None, Decimal | None, SoilLabel]:
    if (
        row.theta_fc is None
        or row.theta_wp is None
        or row.root_depth_m is None
        or row.dry_down_pct is None
    ):
        return None, None, "not_enough_data"
    taw = calc.taw_mm(row.theta_fc, row.theta_wp, row.root_depth_m)
    raw = calc.raw_mm(row.dry_down_pct / Decimal(100), taw)
    return taw, raw, "calculated"


def _class_out(texture: SoilTextureClass | None) -> TextureClassOut | None:
    if texture is None:
        return None
    return TextureClassOut(
        id=texture.id,
        code=texture.code,
        name=LocalizedName(fr=texture.name_fr, ar=texture.name_ar, en=texture.name_en),
    )


def _infiltration_label(source: InfiltrationSource | None) -> InfiltrationLabel:
    if source == InfiltrationSource.ring_test:
        return "measured"
    if source == InfiltrationSource.texture:
        return "estimated"
    return "entered"


def _latest_observed_balance(
    db: Session,
    block_id: uuid.UUID,
    farm_id: uuid.UUID,
) -> WaterBalanceDaily | None:
    return db.scalar(
        select(WaterBalanceDaily)
        .where(
            WaterBalanceDaily.block_id == block_id,
            WaterBalanceDaily.farm_id == farm_id,
            WaterBalanceDaily.is_forecast.is_(False),
        )
        .order_by(WaterBalanceDaily.date.desc())
        .limit(1)
    )


def _stored_pair(
    taw: Decimal | None,
    depletion: Decimal | None,
    raw: Decimal | None,
) -> tuple[Decimal | None, Decimal | None]:
    water_left: Decimal | None = None
    irrigate_below: Decimal | None = None
    if taw is not None and depletion is not None:
        try:
            water_left = calc.water_left_mm(taw, depletion)
        except calc.CalcInputError:
            water_left = None
    if taw is not None and raw is not None:
        try:
            irrigate_below = calc.irrigate_below_mm(taw, raw)
        except calc.CalcInputError:
            irrigate_below = None
    return water_left, irrigate_below


def _soil_out(db: Session, row: SoilProfile) -> SoilOut:
    taw, raw, label = _water_store(row)
    observed = _latest_observed_balance(db, row.block_id, row.farm_id)
    if observed is None:
        water_left, irrigate_below = None, None
    else:
        water_left, irrigate_below = _stored_pair(
            observed.taw_mm,
            observed.depletion_mm,
            observed.raw_mm,
        )
    return SoilOut(
        texture_mode=row.texture_mode,
        texture_class=_class_out(_texture(db, row.texture_class_id)),
        sand_pct=row.sand_pct,
        silt_pct=row.silt_pct,
        clay_pct=row.clay_pct,
        theta_fc=row.theta_fc,
        theta_wp=row.theta_wp,
        root_depth_m=row.root_depth_m,
        dry_down_pct=row.dry_down_pct,
        full_on=row.full_on,
        organic_matter_pct=row.organic_matter_pct,
        compaction=row.compaction,
        infiltration_mm_h=row.infiltration_mm_h,
        infiltration_source=row.infiltration_source,
        taw_mm=taw,
        raw_mm=raw,
        water_left_mm=water_left,
        irrigate_below_mm=irrigate_below,
        label=label,
        sources=SoilSources(infiltration_mm_h=_infiltration_label(row.infiltration_source)),
        version=row.version,
    )


def empty_soil() -> SoilOut:
    return SoilOut(label="not_enough_data", sources=SoilSources())


def read_soil(db: Session, block: Block) -> SoilOut:
    row = _soil_row(db, block)
    if row is None:
        return empty_soil()
    return _soil_out(db, row)


def save_soil(
    db: Session,
    block: Block,
    user: AppUser,
    body: SoilPut,
    if_match: str | None,
) -> SoilOut:
    row = _soil_row(db, block)
    if row is not None:
        _require_if_match(row.version, if_match)
    errors = _soil_errors(db, body)
    errors.update(_reason_error(row is not None, body.reason))
    if errors:
        raise AppError("validation_error", 422, errors)
    texture = _texture(db, body.texture_class_id)
    if row is None:
        row = SoilProfile(
            farm_id=block.farm_id,
            block_id=block.id,
            texture_mode=body.texture_mode,
            version=1,
        )
        db.add(row)
        _apply_soil(row, body, texture)
        db.flush()
        _emit_block(db, block.id, None)
        db.commit()
        db.refresh(row)
        return _soil_out(db, row)
    before = _values(row, _SOIL_FIELDS)
    _apply_soil(row, body, texture)
    row.version += 1
    _add_history(
        db,
        row,
        user,
        _SOIL_ENTITY,
        _changed(before, row, _SOIL_FIELDS),
        _clean_reason(body.reason),
    )
    db.flush()
    _emit_block(db, block.id, None)
    db.commit()
    db.refresh(row)
    return _soil_out(db, row)


def empty_settings() -> IrrigationSettingsOut:
    return IrrigationSettingsOut()


def _settings_out(row: IrrigationSettings) -> IrrigationSettingsOut:
    return IrrigationSettingsOut(
        efficiency=row.efficiency,
        kc=row.kc,
        kc_source=row.kc_source,
        version=row.version,
    )


def read_settings(db: Session, block: Block) -> IrrigationSettingsOut:
    row = _settings_row(db, block)
    if row is None:
        return empty_settings()
    return _settings_out(row)


def save_settings(
    db: Session,
    block: Block,
    user: AppUser,
    body: IrrigationSettingsPut,
    if_match: str | None,
) -> IrrigationSettingsOut:
    row = _settings_row(db, block)
    if row is not None:
        _require_if_match(row.version, if_match)
    errors = _settings_errors(body)
    errors.update(_reason_error(row is not None, body.reason))
    if errors:
        raise AppError("validation_error", 422, errors)
    if row is None:
        row = IrrigationSettings(
            farm_id=block.farm_id,
            block_id=block.id,
            version=1,
        )
        db.add(row)
        _apply_settings(row, body)
        db.flush()
        _emit_block(db, block.id, None)
        db.commit()
        db.refresh(row)
        return _settings_out(row)
    before = _values(row, _SETTINGS_FIELDS)
    _apply_settings(row, body)
    row.version += 1
    _add_history(
        db,
        row,
        user,
        _SETTINGS_ENTITY,
        _changed(before, row, _SETTINGS_FIELDS),
        _clean_reason(body.reason),
    )
    db.flush()
    _emit_block(db, block.id, None)
    db.commit()
    db.refresh(row)
    return _settings_out(row)


_UPSERT_CHUNK = 400

_MISSING_TAW = "soil.taw_missing"
_MISSING_RAW = "soil.raw_missing"
_MISSING_KC = "irrigation.kc_missing"
_MISSING_DEPLETION = "soil.depletion_missing"
_MISSING_ET0 = "weather.et0_missing"
_MISSING_EFFICIENCY = "irrigation.efficiency_missing"
_MISSING_RATE = "irrigation.rate_missing"
_MISSING_FLOW = "irrigation.flow_missing"


def _emit_block(db: Session, block_id: uuid.UUID, from_date: date | None) -> None:
    publish("block.updated", {"db": db, "block_id": block_id, "from_date": from_date})


def _emit_irrigation(db: Session, block_id: uuid.UUID, from_date: date) -> None:
    publish("irrigation.logged", {"db": db, "block_id": block_id, "from_date": from_date})


def _as_date(value: object) -> date | None:
    if type(value) is date:
        return value
    return None


def _on_balance_trigger(payload: dict[str, Any]) -> None:
    db = payload.get("db")
    block_id = payload.get("block_id")
    if not isinstance(db, Session) or not isinstance(block_id, uuid.UUID):
        return
    recompute_balance(db, block_id, _as_date(payload.get("from_date")))


def _on_weather_daily_ready(payload: dict[str, Any]) -> None:
    db = payload.get("db")
    farm_id = payload.get("farm_id")
    if not isinstance(db, Session) or not isinstance(farm_id, uuid.UUID):
        return
    from_date = _as_date(payload.get("from_date"))
    block_ids = db.scalars(select(Block.id).where(Block.farm_id == farm_id)).all()
    for block_id in block_ids:
        recompute_balance(db, block_id, from_date)


def _zone(farm: Farm) -> ZoneInfo:
    return ZoneInfo(farm.timezone)


def _local_date(ts: datetime, zone: ZoneInfo) -> date:
    aware = ts if ts.tzinfo is not None else ts.replace(tzinfo=UTC)
    return aware.astimezone(zone).date()


def _aware(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=UTC)
    return ts


def _farm_today(farm: Farm) -> date:
    return datetime.now(UTC).astimezone(_zone(farm)).date()


def _canon(value: Decimal | None) -> str | None:
    if value is None:
        return None
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _inputs_hash(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _stores(row: SoilProfile | None) -> tuple[Decimal | None, Decimal | None]:
    if row is None or row.theta_fc is None or row.theta_wp is None or row.root_depth_m is None:
        return None, None
    try:
        taw = calc.taw_mm(row.theta_fc, row.theta_wp, row.root_depth_m)
    except calc.CalcInputError:
        return None, None
    if taw <= 0:
        return None, None
    raw = None
    if row.dry_down_pct is not None:
        try:
            raw = calc.raw_mm(row.dry_down_pct / Decimal(100), taw)
        except calc.CalcInputError:
            raw = None
    return taw, raw


def _crop_et(et0: Decimal, kc: Decimal) -> Decimal:
    if et0 == 0:
        return Decimal(0)
    return calc.etc_mm(et0, kc)


def _layout(db: Session, block: Block) -> IrrigationLayout | None:
    return db.scalar(
        select(IrrigationLayout).where(
            IrrigationLayout.block_id == block.id,
            IrrigationLayout.farm_id == block.farm_id,
        )
    )


def _dates(start: date, end: date) -> list[date]:
    days: list[date] = []
    cursor = start
    while cursor <= end:
        days.append(cursor)
        cursor += timedelta(days=1)
    return days


def _series_bounds(
    soil: SoilProfile | None,
    weather_rows: list[WeatherDaily],
    today: date,
) -> tuple[date, date] | None:
    if soil is not None and soil.full_on is not None:
        start = soil.full_on
    elif weather_rows:
        start = min(row.date for row in weather_rows)
    else:
        return None
    forecast = [row.date for row in weather_rows if row.is_forecast and row.date >= start]
    if start <= today:
        end = today if not forecast else max(today, max(forecast))
        return start, end
    if not forecast:
        return None
    return start, max(forecast)


def _balance_notes(soil: SoilProfile | None, rows: list[WaterBalanceDaily]) -> list[str]:
    notes: list[str] = []
    if rows and (soil is None or soil.full_on is None):
        notes.append(f"assumed at field capacity on {rows[0].date.isoformat()}")
    gap = False
    for row in rows:
        if row.depletion_mm is None:
            gap = True
            continue
        if gap:
            notes.append(f"restarted at field capacity on {row.date.isoformat()}")
        gap = False
    return notes


def _day_values(
    block: Block,
    day: date,
    today: date,
    prev: Decimal | None,
    weather: WeatherDaily | None,
    kc: Decimal | None,
    taw: Decimal | None,
    raw: Decimal | None,
    irrigation_soil: Decimal,
    runoff: Decimal,
    reset: Decimal | None,
) -> tuple[dict[str, object], Decimal | None]:
    if day > today:
        irrigation_soil = Decimal(0)
        runoff = Decimal(0)
    et0 = None if weather is None else weather.et0_mm
    rain_obs = None if weather is None else weather.rain_mm
    is_forecast = day >= today
    usable_kc = kc if kc is not None and kc > 0 else None
    usable_et0 = et0 if et0 is not None and et0 >= 0 else None
    usable_taw = taw if taw is not None and taw > 0 else None

    def packed(
        *,
        etc: Decimal | None,
        rain: Decimal | None,
        drainage: Decimal | None,
        depletion: Decimal | None,
        status: WbStatus,
        prev_used: Decimal | None,
    ) -> dict[str, object]:
        digest = _inputs_hash(
            {
                "date": day.isoformat(),
                "dr_prev_mm": _canon(prev_used),
                "et0_mm": _canon(et0 if depletion is None else usable_et0),
                "irrigation_soil_mm": _canon(irrigation_soil),
                "is_forecast": is_forecast,
                "kc": _canon(kc if depletion is None else usable_kc),
                "rain_mm": _canon(rain),
                "raw_mm": _canon(raw),
                "reset_depletion_mm": _canon(reset),
                "runoff_mm": _canon(runoff),
                "taw_mm": _canon(taw if depletion is None else usable_taw),
            }
        )
        return {
            "block_id": block.id,
            "date": day,
            "farm_id": block.farm_id,
            "et0_mm": et0,
            "kc": kc,
            "etc_mm": etc,
            "rain_mm": rain,
            "irrigation_soil_mm": irrigation_soil,
            "runoff_mm": runoff,
            "drainage_mm": drainage,
            "depletion_mm": depletion,
            "taw_mm": taw,
            "raw_mm": raw,
            "status": status,
            "is_forecast": is_forecast,
            "inputs_hash": digest,
        }

    if usable_taw is None or usable_kc is None or usable_et0 is None:
        return packed(
            etc=None,
            rain=rain_obs,
            drainage=None,
            depletion=None,
            status=WbStatus.no_data,
            prev_used=prev,
        ), None
    rain_used = Decimal(0) if rain_obs is None else rain_obs
    started = Decimal(0) if prev is None else prev
    try:
        etc = _crop_et(usable_et0, usable_kc)
        depletion, drainage = calc.daily_balance(
            started,
            rain_used,
            irrigation_soil,
            etc,
            usable_taw,
        )
    except calc.CalcInputError:
        return packed(
            etc=None,
            rain=rain_obs,
            drainage=None,
            depletion=None,
            status=WbStatus.no_data,
            prev_used=prev,
        ), None
    if reset is not None:
        depletion = reset
    if raw is None:
        status = WbStatus.no_data
    else:
        try:
            status = WbStatus(calc.status(depletion, raw))
        except calc.CalcInputError:
            status = WbStatus.no_data
    return packed(
        etc=etc,
        rain=rain_used,
        drainage=drainage,
        depletion=depletion,
        status=status,
        prev_used=started,
    ), depletion


def _upsert_balance(db: Session, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    table = WaterBalanceDaily.__table__
    pk = {"block_id", "date"}
    for offset in range(0, len(rows), _UPSERT_CHUNK):
        chunk = rows[offset : offset + _UPSERT_CHUNK]
        stmt = insert(WaterBalanceDaily).values(chunk)
        excluded = stmt.excluded
        stmt = stmt.on_conflict_do_update(
            index_elements=[table.c.block_id, table.c.date],
            set_={name: getattr(excluded, name) for name in chunk[0] if name not in pk},
        )
        db.execute(stmt)


def recompute_balance(db: Session, block_id: uuid.UUID, from_date: date | None) -> None:
    """Rewrite daily balance rows from ``from_date`` through the forecast.

    ``from_date`` None rebuilds the whole series. The write stays in ``db``;
    the caller commits.
    """
    block = db.get(Block, block_id)
    if block is None:
        return
    farm = db.get(Farm, block.farm_id)
    if farm is None:
        return
    today = _farm_today(farm)
    soil = _soil_row(db, block)
    settings = _settings_row(db, block)
    taw, raw = _stores(soil)
    kc = None if settings is None else settings.kc
    weather_rows = list(
        db.scalars(
            select(WeatherDaily).where(WeatherDaily.farm_id == farm.id).order_by(WeatherDaily.date)
        ).all()
    )
    bounds = _series_bounds(soil, weather_rows, today)
    if bounds is None:
        db.execute(delete(WaterBalanceDaily).where(WaterBalanceDaily.block_id == block.id))
        publish(
            "waterbalance.updated",
            {"db": db, "block_id": block.id, "from_date": None},
        )
        return
    start, end = bounds
    db.execute(
        delete(WaterBalanceDaily).where(
            WaterBalanceDaily.block_id == block.id,
            (WaterBalanceDaily.date < start) | (WaterBalanceDaily.date > end),
        )
    )
    begin = start if from_date is None or from_date <= start else from_date
    prev: Decimal | None = Decimal(0)
    if begin > start:
        anchor = db.scalar(
            select(WaterBalanceDaily).where(
                WaterBalanceDaily.block_id == block.id,
                WaterBalanceDaily.date == begin - timedelta(days=1),
            )
        )
        if anchor is None:
            begin = start
            prev = Decimal(0)
        else:
            prev = anchor.depletion_mm
    by_weather = {row.date: row for row in weather_rows}
    soil_by_day, runoff_by_day = _irrigation_by_day(db, block, _zone(farm))
    reset_by_day = _check_by_day(db, block)
    built: list[dict[str, object]] = []
    for day in _dates(start, end):
        if day < begin:
            continue
        row, prev = _day_values(
            block,
            day,
            today,
            prev,
            by_weather.get(day),
            kc,
            taw,
            raw,
            soil_by_day.get(day, Decimal(0)),
            runoff_by_day.get(day, Decimal(0)),
            reset_by_day.get(day),
        )
        built.append(row)
    _upsert_balance(db, built)
    publish(
        "waterbalance.updated",
        {"db": db, "block_id": block.id, "from_date": begin},
    )


def _irrigation_by_day(
    db: Session,
    block: Block,
    zone: ZoneInfo,
) -> tuple[dict[date, Decimal], dict[date, Decimal]]:
    events = db.scalars(
        select(IrrigationEvent).where(
            IrrigationEvent.block_id == block.id,
            IrrigationEvent.farm_id == block.farm_id,
        )
    ).all()
    soil_by_day: dict[date, Decimal] = {}
    runoff_by_day: dict[date, Decimal] = {}
    for event in events:
        day = _local_date(event.start_at, zone)
        soil_by_day[day] = soil_by_day.get(day, Decimal(0)) + event.soil_mm
        runoff_by_day[day] = runoff_by_day.get(day, Decimal(0)) + event.runoff_mm
    return soil_by_day, runoff_by_day


def _check_by_day(db: Session, block: Block) -> dict[date, Decimal]:
    checks = db.scalars(
        select(SoilCheck)
        .where(SoilCheck.block_id == block.id, SoilCheck.farm_id == block.farm_id)
        .order_by(SoilCheck.created_at, SoilCheck.id)
    ).all()
    latest: dict[date, Decimal] = {}
    for check in checks:
        latest[check.date] = check.reset_depletion_mm
    return latest


def _chosen_valves(db: Session, block: Block, valve_ids: list[uuid.UUID]) -> list[Valve]:
    unique_ids = list(dict.fromkeys(valve_ids))
    found = db.scalars(
        select(Valve).where(
            Valve.id.in_(unique_ids),
            Valve.block_id == block.id,
            Valve.farm_id == block.farm_id,
        )
    ).all()
    by_id = {row.id: row for row in found}
    if len(by_id) != len(unique_ids):
        raise AppError("validation_error", 422, {"valve_ids": "irrigation.valve_not_found"})
    return [by_id[valve_id] for valve_id in unique_ids]


def _run_amounts(
    db: Session,
    block: Block,
    valve_ids: list[uuid.UUID],
    duration_min: int,
) -> tuple[list[uuid.UUID], Decimal, Decimal, Decimal, Decimal]:
    valves = _chosen_valves(db, block, valve_ids)
    layout = _layout(db, block)
    rate = None if layout is None else layout.rate_mm_h
    settings = _settings_row(db, block)
    efficiency = None if settings is None else settings.efficiency
    ready = (
        rate is not None
        and rate > 0
        and efficiency is not None
        and efficiency > 0
        and efficiency <= 1
        and all(valve.q_m3h is not None and valve.q_m3h > 0 for valve in valves)
    )
    if not ready:
        raise AppError("validation_error", 422, {"irrigation": "irrigation.block_not_ready"})
    flow = sum((valve.q_m3h for valve in valves if valve.q_m3h is not None), Decimal(0))
    if flow <= 0 or rate is None or efficiency is None:
        raise AppError("validation_error", 422, {"irrigation": "irrigation.block_not_ready"})
    soil = _soil_row(db, block)
    infiltration = None if soil is None else soil.infiltration_mm_h
    duration = Decimal(duration_min)
    try:
        depth = calc.depth_mm(rate, duration)
        volume = calc.volume_m3(flow, duration)
        soil_mm, runoff_mm = calc.soil_entering(rate, duration, efficiency, infiltration)
    except calc.CalcInputError as exc:
        raise AppError("validation_error", 422, {exc.field: exc.code}) from None
    return [valve.id for valve in valves], depth, volume, soil_mm, runoff_mm


def _event_or_404(db: Session, block: Block, event_id: uuid.UUID) -> IrrigationEvent:
    row = db.scalar(
        select(IrrigationEvent).where(
            IrrigationEvent.id == event_id,
            IrrigationEvent.block_id == block.id,
            IrrigationEvent.farm_id == block.farm_id,
        )
    )
    if row is None:
        raise AppError("irrigation.not_found", 404)
    return row


def _event_out(row: IrrigationEvent) -> IrrigationEventOut:
    return IrrigationEventOut(
        id=row.id,
        block_id=row.block_id,
        valve_ids=list(row.valve_ids),
        start_at=row.start_at,
        duration_min=row.duration_min,
        depth_mm=row.depth_mm,
        volume_m3=row.volume_m3,
        soil_mm=row.soil_mm,
        runoff_mm=row.runoff_mm,
        source=row.source,
        version=row.version,
    )


def _event_rows(db: Session, block: Block) -> list[IrrigationEvent]:
    return list(
        db.scalars(
            select(IrrigationEvent)
            .where(
                IrrigationEvent.block_id == block.id,
                IrrigationEvent.farm_id == block.farm_id,
            )
            .order_by(IrrigationEvent.start_at.desc(), IrrigationEvent.id.desc())
        ).all()
    )


def list_irrigation_events(
    db: Session,
    block: Block,
    from_date: date | None = None,
    to_date: date | None = None,
    limit: int | None = None,
) -> IrrigationEventsOut:
    """List irrigation events and sum depth, volume and soil water on the server.

    ``from`` and ``to`` are farm-local dates of ``start_at``. Totals cover every
    event in that window. ``limit`` shortens the returned list only.
    """
    farm = db.get(Farm, block.farm_id)
    if farm is None:
        raise AppError("farm.not_found", 404)
    zone = _zone(farm)
    rows = _event_rows(db, block)
    if from_date is not None:
        rows = [row for row in rows if _local_date(row.start_at, zone) >= from_date]
    if to_date is not None:
        rows = [row for row in rows if _local_date(row.start_at, zone) <= to_date]
    totals = IrrigationTotalsOut(
        count=len(rows),
        depth_mm=sum((row.depth_mm for row in rows), Decimal(0)),
        volume_m3=sum((row.volume_m3 for row in rows), Decimal(0)),
        soil_mm=sum((row.soil_mm for row in rows), Decimal(0)),
    )
    shown = rows if limit is None else rows[:limit]
    return IrrigationEventsOut(events=[_event_out(row) for row in shown], totals=totals)


def preview_irrigation(
    db: Session,
    user: AppUser,
    body: IrrigationPreviewIn,
) -> IrrigationPreviewOut:
    """Return the same depths and volume as logging an irrigation, without writing."""
    block = db.get(Block, body.block_id)
    if block is None or block.farm.owner_user_id != user.id:
        raise AppError("block.not_found", 404)
    _valve_ids, depth, volume, soil_mm, runoff_mm = _run_amounts(
        db,
        block,
        body.valve_ids,
        body.duration_min,
    )
    return IrrigationPreviewOut(
        depth_mm=depth,
        volume_m3=volume,
        soil_mm=soil_mm,
        runoff_mm=runoff_mm,
    )


def create_irrigation_event(
    db: Session,
    block: Block,
    user: AppUser,
    body: IrrigationEventIn,
) -> IrrigationEventOut:
    valve_ids, depth, volume, soil_mm, runoff_mm = _run_amounts(
        db,
        block,
        body.valve_ids,
        body.duration_min,
    )
    farm = db.get(Farm, block.farm_id)
    if farm is None:
        raise AppError("farm.not_found", 404)
    row = IrrigationEvent(
        farm_id=block.farm_id,
        block_id=block.id,
        valve_ids=valve_ids,
        start_at=_aware(body.start_at),
        duration_min=body.duration_min,
        depth_mm=depth,
        volume_m3=volume,
        soil_mm=soil_mm,
        runoff_mm=runoff_mm,
        source=IrrigationSource.calculated,
        entered_by=user.id,
        version=1,
        updated_at=datetime.now(UTC),
    )
    db.add(row)
    db.flush()
    _emit_irrigation(db, block.id, _local_date(row.start_at, _zone(farm)))
    db.commit()
    db.refresh(row)
    return _event_out(row)


def update_irrigation_event(
    db: Session,
    block: Block,
    event_id: uuid.UUID,
    body: IrrigationEventPatch,
    if_match: str | None,
) -> IrrigationEventOut:
    row = _event_or_404(db, block, event_id)
    _require_if_match(row.version, if_match)
    farm = db.get(Farm, block.farm_id)
    if farm is None:
        raise AppError("farm.not_found", 404)
    zone = _zone(farm)
    old_day = _local_date(row.start_at, zone)
    valve_ids = list(row.valve_ids) if body.valve_ids is None else body.valve_ids
    start_at = row.start_at if body.start_at is None else body.start_at
    duration_min = row.duration_min if body.duration_min is None else body.duration_min
    stored_ids, depth, volume, soil_mm, runoff_mm = _run_amounts(
        db,
        block,
        valve_ids,
        duration_min,
    )
    row.valve_ids = stored_ids
    row.start_at = _aware(start_at)
    row.duration_min = duration_min
    row.depth_mm = depth
    row.volume_m3 = volume
    row.soil_mm = soil_mm
    row.runoff_mm = runoff_mm
    row.source = IrrigationSource.calculated
    row.version += 1
    row.updated_at = datetime.now(UTC)
    db.flush()
    new_day = _local_date(row.start_at, zone)
    _emit_irrigation(db, block.id, min(old_day, new_day))
    db.commit()
    db.refresh(row)
    return _event_out(row)


def delete_irrigation_event(
    db: Session,
    block: Block,
    event_id: uuid.UUID,
    if_match: str | None,
) -> None:
    row = _event_or_404(db, block, event_id)
    _require_if_match(row.version, if_match)
    farm = db.get(Farm, block.farm_id)
    if farm is None:
        raise AppError("farm.not_found", 404)
    day = _local_date(row.start_at, _zone(farm))
    db.delete(row)
    db.flush()
    _emit_irrigation(db, block.id, day)
    db.commit()


def preview_soil_check(db: Session, block: Block, feel: SoilFeel) -> SoilCheckPreviewOut:
    """Depletion reset, water left and percent of TAW for a feel band. No write."""
    taw, _raw = _stores(_soil_row(db, block))
    if taw is None:
        raise AppError("validation_error", 422, {"taw_mm": "soil.taw_missing"})
    try:
        reset = calc.soil_check_reset_mm(taw, feel)
    except calc.CalcInputError as exc:
        raise AppError("validation_error", 422, {exc.field: exc.code}) from None
    water_left = calc.water_left_mm(taw, reset)
    return SoilCheckPreviewOut(
        reset_depletion_mm=reset,
        water_left_mm=water_left,
        pct_of_taw=water_left / taw * Decimal(100),
    )


def create_soil_check(db: Session, block: Block, body: SoilCheckIn) -> SoilCheckOut:
    taw, _raw = _stores(_soil_row(db, block))
    if taw is None:
        raise AppError("validation_error", 422, {"taw_mm": "soil.not_enough_data"})
    try:
        reset = calc.soil_check_reset_mm(taw, body.feel)
    except calc.CalcInputError as exc:
        raise AppError("validation_error", 422, {exc.field: exc.code}) from None
    row = SoilCheck(
        farm_id=block.farm_id,
        block_id=block.id,
        date=body.date,
        depth_band=body.depth_band,
        feel=body.feel,
        reset_depletion_mm=reset,
    )
    db.add(row)
    db.flush()
    _emit_block(db, block.id, body.date)
    db.commit()
    db.refresh(row)
    return SoilCheckOut(
        id=row.id,
        block_id=row.block_id,
        date=row.date,
        depth_band=row.depth_band,
        feel=row.feel,
        reset_depletion_mm=row.reset_depletion_mm,
        created_at=row.created_at,
    )


def _row_out(row: WaterBalanceDaily) -> WaterBalanceRowOut:
    water_left, irrigate_below = _stored_pair(row.taw_mm, row.depletion_mm, row.raw_mm)
    return WaterBalanceRowOut(
        date=row.date,
        et0_mm=row.et0_mm,
        kc=row.kc,
        etc_mm=row.etc_mm,
        rain_mm=row.rain_mm,
        irrigation_soil_mm=row.irrigation_soil_mm,
        runoff_mm=row.runoff_mm,
        drainage_mm=row.drainage_mm,
        depletion_mm=row.depletion_mm,
        taw_mm=row.taw_mm,
        raw_mm=row.raw_mm,
        water_left_mm=water_left,
        irrigate_below_mm=irrigate_below,
        status=row.status,
        is_forecast=row.is_forecast,
        inputs_hash=row.inputs_hash,
    )


def _period_bounds(
    today: date,
    period: BalancePeriod,
    soil: SoilProfile | None,
    rows: list[WaterBalanceDaily],
) -> tuple[date | None, date | None]:
    """Farm-local window for a balance period.

    Week is Monday through Sunday of the week that contains ``today``. Month
    is that calendar month. Season starts on ``soil.full_on``, or on the first
    balance day when the soil has no full date, and has no end.
    """
    if period == "week":
        start = today - timedelta(days=today.weekday())
        return start, start + timedelta(days=6)
    if period == "month":
        start = today.replace(day=1)
        if start.month == 12:
            next_month = date(start.year + 1, 1, 1)
        else:
            next_month = date(start.year, start.month + 1, 1)
        return start, next_month - timedelta(days=1)
    if soil is not None and soil.full_on is not None:
        return soil.full_on, None
    if rows:
        return rows[0].date, None
    return None, None


def read_water_balance(
    db: Session,
    block: Block,
    from_date: date | None,
    to_date: date | None,
    period: BalancePeriod | None = None,
) -> WaterBalanceOut:
    rows = list(
        db.scalars(
            select(WaterBalanceDaily)
            .where(
                WaterBalanceDaily.block_id == block.id,
                WaterBalanceDaily.farm_id == block.farm_id,
            )
            .order_by(WaterBalanceDaily.date)
        ).all()
    )
    soil = _soil_row(db, block)
    notes = _balance_notes(soil, rows)
    if period is not None and from_date is None and to_date is None:
        farm = db.get(Farm, block.farm_id)
        if farm is not None:
            from_date, to_date = _period_bounds(_farm_today(farm), period, soil, rows)
    if from_date is not None:
        rows = [row for row in rows if row.date >= from_date]
    if to_date is not None:
        rows = [row for row in rows if row.date <= to_date]
    return WaterBalanceOut(rows=[_row_out(row) for row in rows], notes=notes)


def _balance_on(db: Session, block: Block, day: date) -> WaterBalanceDaily | None:
    return db.scalar(
        select(WaterBalanceDaily).where(
            WaterBalanceDaily.block_id == block.id,
            WaterBalanceDaily.farm_id == block.farm_id,
            WaterBalanceDaily.date == day,
        )
    )


def _dose(
    net: Decimal | None,
    efficiency: Decimal | None,
    rate: Decimal | None,
    flow: Decimal | None,
) -> DoseOut:
    gross: Decimal | None = None
    runtime: Decimal | None = None
    volume: Decimal | None = None
    if net is not None and efficiency is not None:
        if net == 0:
            gross = Decimal(0)
        elif net > 0:
            try:
                gross = calc.gross_mm(net, efficiency)
            except calc.CalcInputError:
                gross = None
    if gross is not None and rate is not None:
        if gross == 0:
            runtime = Decimal(0)
        elif gross > 0:
            try:
                runtime = calc.run_time_min(gross, rate)
            except calc.CalcInputError:
                runtime = None
    if runtime is not None and flow is not None:
        if runtime == 0:
            volume = Decimal(0)
        elif runtime > 0:
            try:
                volume = calc.volume_m3(flow, runtime)
            except calc.CalcInputError:
                volume = None
    return DoseOut(net_mm=net, gross_mm=gross, run_time_min=runtime, volume_m3=volume)


def read_irrigation_today(db: Session, block: Block) -> IrrigationTodayOut:
    farm = db.get(Farm, block.farm_id)
    if farm is None:
        raise AppError("farm.not_found", 404)
    today = _farm_today(farm)
    soil = _soil_row(db, block)
    settings = _settings_row(db, block)
    taw, raw = _stores(soil)
    kc = None if settings is None else settings.kc
    yesterday = _balance_on(db, block, today - timedelta(days=1))
    today_row = _balance_on(db, block, today)
    weather_today = db.scalar(
        select(WeatherDaily).where(
            WeatherDaily.farm_id == block.farm_id,
            WeatherDaily.date == today,
        )
    )
    layout = _layout(db, block)
    missing: list[str] = []
    if taw is None:
        missing.append(_MISSING_TAW)
    if raw is None:
        missing.append(_MISSING_RAW)
    if kc is None or kc <= 0:
        missing.append(_MISSING_KC)
        kc = None
    depletion = None if yesterday is None else yesterday.depletion_mm
    if depletion is None and soil is not None and soil.full_on == today:
        depletion = Decimal(0)
    elif depletion is None:
        missing.append(_MISSING_DEPLETION)
    et0 = None if weather_today is None else weather_today.et0_mm
    if today_row is not None and today_row.et0_mm is not None:
        et0 = today_row.et0_mm
    if et0 is None or et0 < 0:
        missing.append(_MISSING_ET0)
        et0 = None
    etc: Decimal | None = None
    if et0 is not None and kc is not None:
        try:
            etc = _crop_et(et0, kc)
        except calc.CalcInputError:
            etc = None
            if _MISSING_ET0 not in missing:
                missing.append(_MISSING_ET0)
    efficiency = None if settings is None else settings.efficiency
    if efficiency is None or efficiency <= 0 or efficiency > 1:
        missing.append(_MISSING_EFFICIENCY)
        efficiency = None
    rate = None if layout is None else layout.rate_mm_h
    if rate is None or rate <= 0:
        missing.append(_MISSING_RATE)
        rate = None
    flow = None if layout is None else layout.q_block_m3h
    if flow is None or flow <= 0:
        missing.append(_MISSING_FLOW)
        flow = None
    if depletion is None or raw is None:
        status = WbStatus.no_data
    else:
        try:
            status = WbStatus(calc.status(depletion, raw))
        except calc.CalcInputError:
            status = WbStatus.no_data
    recommended = "refill" if status == WbStatus.irrigate_soon else "maintain"
    refill_net = None if depletion is None or etc is None else depletion + etc
    label = "no_data" if missing or status == WbStatus.no_data else "calculated"
    water_left, irrigate_below = _stored_pair(taw, depletion, raw)
    return IrrigationTodayOut(
        date=today,
        depletion_mm=depletion,
        taw_mm=taw,
        raw_mm=raw,
        water_left_mm=water_left,
        irrigate_below_mm=irrigate_below,
        etc_today_mm=etc,
        status=status,
        refill=_dose(refill_net, efficiency, rate, flow),
        maintain=_dose(etc, efficiency, rate, flow),
        recommended=recommended,
        label=label,
        missing=missing,
    )


def read_farm_irrigation_today(db: Session, farm: Farm) -> FarmIrrigationTodayOut:
    blocks = db.scalars(
        select(Block).where(Block.farm_id == farm.id).order_by(Block.name, Block.id)
    ).all()
    items: list[BlockIrrigationTodayOut] = []
    for block in blocks:
        item = read_irrigation_today(db, block)
        items.append(
            BlockIrrigationTodayOut(
                block_id=block.id,
                date=item.date,
                depletion_mm=item.depletion_mm,
                taw_mm=item.taw_mm,
                raw_mm=item.raw_mm,
                water_left_mm=item.water_left_mm,
                irrigate_below_mm=item.irrigate_below_mm,
                etc_today_mm=item.etc_today_mm,
                status=item.status,
                refill=item.refill,
                maintain=item.maintain,
                recommended=item.recommended,
                label=item.label,
                missing=list(item.missing),
            )
        )
    return FarmIrrigationTodayOut(date=_farm_today(farm), blocks=items)


_registered = False


def register_handlers() -> None:
    global _registered
    if _registered:
        return
    subscribe("block.updated", _on_balance_trigger)
    subscribe("irrigation.logged", _on_balance_trigger)
    subscribe("weather.daily_ready", _on_weather_daily_ready)
    _registered = True


register_handlers()
