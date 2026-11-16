"""Block persistence. Area and bearing are calculated in PostGIS on every save.

Planting, irrigation layout, and valve totals are derived in recompute_block.
"""

import hashlib
import json
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.modules.auth.models import AppUser
from app.modules.catalog.models import Crop, TrainingSystem, Variety
from app.modules.catalog.schemas import LocalizedName
from app.modules.farms.models import Farm
from app.modules.registry import calc
from app.modules.registry.calc import CalcInputError
from app.modules.registry.models import (
    Block,
    BlockStatus,
    DensityInput,
    FlowEntryMode,
    IrrigationLayout,
    Planting,
    RecordVersion,
    TypedFlowBasis,
    Valve,
)
from app.modules.registry.schemas import (
    BlockCreate,
    BlockCropOut,
    BlockHistoryOut,
    BlockListItem,
    BlockOut,
    BlockSources,
    BlockUpdate,
    BlockValveOut,
    IrrigationLayoutOut,
    IrrigationLayoutPut,
    IrrigationLayoutSources,
    PlantingIn,
    PlantingOut,
    PlantingSources,
    PlantingsPut,
    SourceLabel,
    ValveSources,
    ValvesPut,
    ValveWrite,
    format_area_ha,
    format_bearing_deg,
    format_flow_m3h,
    format_rate_mm_h,
)

_BLOCK_ENTITY = "block"

# Identifiers interpolated into the measure SQL. Never pass user text here.
_GEOM_SQL = frozenset({"g", "outline", "row_line"})


def geometry_measure_sql(geom: str) -> tuple[str, str]:
    """Gross area (ha) and undirected row bearing for one geometry expression.

    gross_area_ha = ST_Area(geom::geography) / 10000, numeric(12, 4)
    row_bearing_deg = mod(degrees(ST_Azimuth(start::geography, end::geography)) + 180, 180)
    folded into [0, 180). degrees() is double precision and mod() has no float
    overload, so the azimuth sum is cast to numeric. A value that rounds to 180
    is folded to 0.

    Block save and POST /v1/calc/registry/geometry both use this helper.
    Source: AGRECT registry block save (D-035).
    """
    if geom not in _GEOM_SQL:
        raise ValueError("unknown geometry expression")
    area = f"CAST(ST_Area(CAST({geom} AS geography)) / 10000 AS numeric(12, 4))"
    bearing = (
        "mod(CAST(mod(CAST(degrees(ST_Azimuth("
        f"CAST(ST_StartPoint({geom}) AS geography), "
        f"CAST(ST_EndPoint({geom}) AS geography)"
        ")) + 180 AS numeric), 180) AS numeric(6, 2)), 180)"
    )
    return area, bearing


_OUTLINE_AREA_TEMPLATE = """
    SELECT
        ST_GeometryType(g) AS gtype,
        ST_IsValid(g) AS is_valid,
        ST_Area(CAST(g AS geography)) > 0 AS has_area,
        __AREA__ AS area_ha
    FROM (
        SELECT ST_SetSRID(ST_GeomFromGeoJSON(:geo), 4326) AS g
    ) AS src
    """

_RECALC_TEMPLATE = """
    UPDATE block
    SET gross_area_ha = CASE
            WHEN outline IS NULL THEN NULL
            ELSE __AREA__
        END,
        row_bearing_deg = CASE
            WHEN row_line IS NULL THEN NULL
            ELSE __BEARING__
        END
    WHERE id = :id
    RETURNING gross_area_ha, row_bearing_deg
    """

_BEARING_TEMPLATE = """
    SELECT __BEARING__ AS row_bearing_deg
    FROM (
        SELECT ST_SetSRID(ST_GeomFromGeoJSON(:geo), 4326) AS g
    ) AS src
    """


def _outline_area_sql() -> str:
    area, _bearing = geometry_measure_sql("g")
    return _OUTLINE_AREA_TEMPLATE.replace("__AREA__", area)


def _recalc_sql() -> str:
    area, _bearing = geometry_measure_sql("outline")
    _area, bearing = geometry_measure_sql("row_line")
    return _RECALC_TEMPLATE.replace("__AREA__", area).replace("__BEARING__", bearing)


def _bearing_sql() -> str:
    _area, bearing = geometry_measure_sql("g")
    return _BEARING_TEMPLATE.replace("__BEARING__", bearing)


_OUTLINE_SQL = text(_outline_area_sql())

_LINE_SQL = text(
    """
    SELECT
        ST_GeometryType(g) AS gtype,
        (
            SELECT count(*)
            FROM (
                SELECT DISTINCT dp.geom
                FROM ST_DumpPoints(g) AS dp
            ) AS pts
        ) AS distinct_points
    FROM (
        SELECT ST_SetSRID(ST_GeomFromGeoJSON(:geo), 4326) AS g
    ) AS src
    """
)

_RECALC = text(_recalc_sql())
_BEARING_SQL = text(_bearing_sql())


def _quantize_area(value: Decimal | None) -> Decimal | None:
    if value is None:
        return None
    return value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def _clean_reason(reason: str | None) -> str | None:
    if reason is None:
        return None
    stripped = reason.strip()
    if not stripped:
        return None
    return stripped


def _require_if_match(block: Block, if_match: str | None) -> None:
    if if_match is None or if_match.strip() == "":
        raise AppError("conflict.version_required", 428)
    token = if_match.strip()
    if len(token) >= 2 and token[0] == '"' and token[-1] == '"':
        token = token[1:-1]
    try:
        presented = int(token)
    except ValueError:
        raise AppError("conflict.version", 409) from None
    if presented != block.version:
        raise AppError("conflict.version", 409)


def _dump_geojson(geojson: dict[str, Any]) -> str | None:
    try:
        return json.dumps(geojson)
    except (TypeError, ValueError):
        return None


def _from_geojson(geojson: dict[str, Any]) -> Any:
    return func.ST_SetSRID(func.ST_GeomFromGeoJSON(json.dumps(geojson)), 4326)


def _geometry_fault(exc: SQLAlchemyError) -> bool:
    orig = getattr(exc, "orig", None)
    sqlstate = getattr(orig, "sqlstate", None)
    return isinstance(sqlstate, str) and (sqlstate.startswith("22") or sqlstate == "XX000")


def _run_geo(db: Session, statement: Any, params: dict[str, object]) -> Any:
    try:
        with db.begin_nested():
            return db.execute(statement, params).one()
    except SQLAlchemyError as exc:
        if _geometry_fault(exc):
            return None
        raise


def _as_decimal(value: object) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _inspect_outline(db: Session, geojson: dict[str, Any]) -> tuple[str | None, Decimal | None]:
    payload = _dump_geojson(geojson)
    if payload is None:
        return "block.outline_invalid", None
    row = _run_geo(db, _OUTLINE_SQL, {"geo": payload})
    if (
        row is None
        or row.gtype != "ST_Polygon"
        or row.is_valid is not True
        or row.has_area is not True
        or row.area_ha is None
    ):
        return "block.outline_invalid", None
    return None, _as_decimal(row.area_ha)


def _inspect_row_line(db: Session, geojson: dict[str, Any]) -> str | None:
    payload = _dump_geojson(geojson)
    if payload is None:
        return "block.row_line_invalid"
    row = _run_geo(db, _LINE_SQL, {"geo": payload})
    if row is None or row.gtype != "ST_LineString" or int(row.distinct_points) < 2:
        return "block.row_line_invalid"
    return None


def _pair_intersects(
    db: Session,
    block_id: uuid.UUID | None,
    outline: dict[str, Any] | None,
    row_line: dict[str, Any] | None,
    *,
    outline_from_row: bool,
    line_from_row: bool,
) -> bool:
    if outline_from_row:
        outline_expr = Block.outline
    elif outline is None:
        return False
    else:
        outline_expr = _from_geojson(outline)
    if line_from_row:
        line_expr = Block.row_line
    elif row_line is None:
        return False
    else:
        line_expr = _from_geojson(row_line)
    stmt = select(func.ST_Intersects(outline_expr, line_expr))
    if outline_from_row or line_from_row:
        stmt = stmt.where(Block.id == block_id)
    try:
        with db.begin_nested():
            found = db.scalar(stmt)
    except SQLAlchemyError as exc:
        if _geometry_fault(exc):
            return False
        raise
    return found is True


def _geometry_errors(
    db: Session,
    *,
    block_id: uuid.UUID | None,
    outline: dict[str, Any] | None,
    row_line: dict[str, Any] | None,
    outline_provided: bool,
    row_line_provided: bool,
    has_outline: bool,
    has_row_line: bool,
    current_area_ha: Decimal | None,
) -> tuple[dict[str, str], Decimal | None]:
    errors: dict[str, str] = {}
    if outline_provided:
        if outline is None:
            area = None
        else:
            problem, area = _inspect_outline(db, outline)
            if problem is not None:
                errors["outline"] = problem
                area = None
    else:
        area = current_area_ha

    if row_line_provided and row_line is not None:
        problem = _inspect_row_line(db, row_line)
        if problem is not None:
            errors["row_line"] = problem

    outline_exists = outline is not None if outline_provided else has_outline
    line_exists = row_line is not None if row_line_provided else has_row_line
    if "outline" not in errors and "row_line" not in errors and outline_exists and line_exists:
        intersects = _pair_intersects(
            db,
            block_id,
            outline,
            row_line,
            outline_from_row=not outline_provided,
            line_from_row=not row_line_provided,
        )
        if not intersects:
            errors["row_line"] = "block.row_line_outside"
    return errors, area


def _name_taken(db: Session, farm_id: uuid.UUID, name: str, block_id: uuid.UUID | None) -> bool:
    stmt = select(Block.id).where(Block.farm_id == farm_id, Block.name == name)
    if block_id is not None:
        stmt = stmt.where(Block.id != block_id)
    return db.scalar(stmt) is not None


def _catalog_errors(
    db: Session,
    crop_id: uuid.UUID | None,
    training_system_id: uuid.UUID | None,
) -> dict[str, str]:
    errors: dict[str, str] = {}
    crop = db.get(Crop, crop_id) if crop_id is not None else None
    if crop_id is not None and crop is None:
        errors["crop_id"] = "catalog.crop_not_found"
    if training_system_id is not None:
        system = db.get(TrainingSystem, training_system_id)
        if system is None or crop is None or system.crop_id != crop.id:
            errors["training_system_id"] = "block.training_system_mismatch"
    return errors


def _net_errors(net_area_ha: Decimal | None, gross_area_ha: Decimal | None) -> dict[str, str]:
    if net_area_ha is None:
        return {}
    if net_area_ha <= 0:
        return {"net_area_ha": "block.net_area_must_be_positive"}
    if gross_area_ha is not None and net_area_ha > gross_area_ha:
        return {"net_area_ha": "block.net_area_exceeds_gross"}
    return {}


def _field_errors(
    db: Session,
    *,
    farm_id: uuid.UUID,
    block_id: uuid.UUID | None,
    name: str | None,
    status: BlockStatus,
    reason: str | None,
    crop_id: uuid.UUID | None,
    training_system_id: uuid.UUID | None,
    net_area_ha: Decimal | None,
    outline: dict[str, Any] | None,
    row_line: dict[str, Any] | None,
    outline_provided: bool,
    row_line_provided: bool,
    has_outline: bool,
    has_row_line: bool,
    current_area_ha: Decimal | None,
) -> dict[str, str]:
    errors: dict[str, str] = {}
    if status == BlockStatus.complete and _clean_reason(reason) is None:
        errors["reason"] = "record.reason_required"
    if name is None or name.strip() == "":
        errors["name"] = "block.name_required"
    elif _name_taken(db, farm_id, name, block_id):
        errors["name"] = "block.name_taken"
    errors.update(_catalog_errors(db, crop_id, training_system_id))
    geometry_errors, area_ha = _geometry_errors(
        db,
        block_id=block_id,
        outline=outline,
        row_line=row_line,
        outline_provided=outline_provided,
        row_line_provided=row_line_provided,
        has_outline=has_outline,
        has_row_line=has_row_line,
        current_area_ha=current_area_ha,
    )
    errors.update(geometry_errors)
    if "net_area_ha" not in errors:
        errors.update(_net_errors(net_area_ha, area_ha))
    return errors


def _recalculate(db: Session, block_id: uuid.UUID) -> tuple[Decimal | None, Decimal | None]:
    """Store gross area and undirected row bearing from the saved geometry.

    Uses geometry_measure_sql. Rows have no direction: 0 = N–S, 90 = E–W,
    range [0, 180). Both are null when their geometry is null.
    """
    row = db.execute(_RECALC, {"id": block_id}).one()
    gross = None if row.gross_area_ha is None else _as_decimal(row.gross_area_ha)
    bearing = None if row.row_bearing_deg is None else _as_decimal(row.row_bearing_deg)
    return gross, bearing


def preview_geometry(
    db: Session,
    outline: dict[str, Any] | None,
    row_line: dict[str, Any] | None,
) -> tuple[Decimal | None, Decimal | None]:
    """Measure unsaved outline and row line. Reads PostGIS; writes nothing.

    Area and bearing use geometry_measure_sql, the same expressions as block save.
    """
    errors, area = _geometry_errors(
        db,
        block_id=None,
        outline=outline,
        row_line=row_line,
        outline_provided=True,
        row_line_provided=True,
        has_outline=False,
        has_row_line=False,
        current_area_ha=None,
    )
    if errors:
        raise AppError("validation_error", 422, errors)
    if row_line is None:
        return area, None
    payload = _dump_geojson(row_line)
    if payload is None:
        raise AppError("validation_error", 422, {"row_line": "block.row_line_invalid"})
    row = _run_geo(db, _BEARING_SQL, {"geo": payload})
    if row is None or row.row_bearing_deg is None:
        raise AppError("validation_error", 422, {"row_line": "block.row_line_invalid"})
    return area, _as_decimal(row.row_bearing_deg)


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        orig = exc.orig
        constraint = str(getattr(getattr(orig, "diag", None), "constraint_name", "") or orig)
        if "uq_block_farm_id" in constraint:
            raise AppError("validation_error", 422, {"name": "block.name_taken"}) from None
        raise


def _geometry_changed(
    db: Session,
    column: Any,
    block_id: uuid.UUID,
    new_geojson: dict[str, Any] | None,
) -> bool:
    if new_geojson is None:
        is_null = db.scalar(select(column.is_(None)).where(Block.id == block_id))
        return is_null is not True
    try:
        with db.begin_nested():
            equals = db.scalar(
                select(func.ST_Equals(column, _from_geojson(new_geojson))).where(
                    Block.id == block_id
                )
            )
    except SQLAlchemyError as exc:
        if _geometry_fault(exc):
            return True
        raise
    return equals is not True


def _snapshot(block: Block) -> dict[str, object]:
    return {
        "name": block.name,
        "status": block.status,
        "gross_area_ha": block.gross_area_ha,
        "row_bearing_deg": block.row_bearing_deg,
        "net_area_ha": _quantize_area(block.net_area_ha),
        "rows_total": block.rows_total,
        "crop_id": block.crop_id,
        "training_system_id": block.training_system_id,
        "training_other": block.training_other,
    }


def _changed_fields(
    before: dict[str, object],
    block: Block,
    gross_area_ha: Decimal | None,
    row_bearing_deg: Decimal | None,
    *,
    outline_changed: bool,
    row_line_changed: bool,
) -> list[str]:
    changed: list[str] = []
    if before["name"] != block.name:
        changed.append("name")
    if before["status"] != block.status:
        changed.append("status")
    if outline_changed:
        changed.append("outline")
    if row_line_changed:
        changed.append("row_line")
    if before["gross_area_ha"] != gross_area_ha:
        changed.append("gross_area_ha")
    if before["row_bearing_deg"] != row_bearing_deg:
        changed.append("row_bearing_deg")
    if before["net_area_ha"] != _quantize_area(block.net_area_ha):
        changed.append("net_area_ha")
    if before["rows_total"] != block.rows_total:
        changed.append("rows_total")
    if before["crop_id"] != block.crop_id:
        changed.append("crop_id")
    if before["training_system_id"] != block.training_system_id:
        changed.append("training_system_id")
    if before["training_other"] != block.training_other:
        changed.append("training_other")
    return changed


def _remember_calculated(
    block: Block,
    gross_area_ha: Decimal | None,
    row_bearing_deg: Decimal | None,
) -> None:
    block.gross_area_ha = gross_area_ha
    block.row_bearing_deg = row_bearing_deg


def _write_calculated(db: Session, block: Block) -> tuple[Decimal | None, Decimal | None]:
    db.flush()
    db.expire(block, ["outline", "row_line"])
    gross_area_ha, row_bearing_deg = _recalculate(db, block.id)
    problem = _net_errors(block.net_area_ha, gross_area_ha)
    if problem:
        db.rollback()
        raise AppError("validation_error", 422, problem)
    _remember_calculated(block, gross_area_ha, row_bearing_deg)
    return gross_area_ha, row_bearing_deg


def _add_history(
    db: Session,
    block: Block,
    user: AppUser,
    changed: list[str],
    reason: str | None,
) -> None:
    db.add(
        RecordVersion(
            farm_id=block.farm_id,
            entity_type=_BLOCK_ENTITY,
            entity_id=block.id,
            version=block.version,
            changed_fields=changed,
            reason=reason,
            user_id=user.id,
            changed_at=datetime.now(UTC),
        )
    )


def _require_name(name: str | None) -> str:
    if name is None or name.strip() == "":
        raise AppError("validation_error", 422, {"name": "block.name_required"})
    return name


_PLANTING_FIELDS = (
    "variety_id",
    "variety_text",
    "rootstock",
    "planting_year",
    "density_input",
    "row_spacing_m",
    "tree_spacing_m",
    "trees_per_ha",
    "trees_count",
    "area_ha",
)

_LAYOUT_FIELDS = (
    "system",
    "entry_mode",
    "laterals_per_row",
    "emitter_spacing_m",
    "emitter_flow_lph",
    "emitters_per_tree",
    "flow_per_emitter_lph",
    "typed_flow_m3h",
    "typed_flow_basis",
    "flow_meter",
    "q_ha_m3h",
    "q_block_m3h",
    "rate_mm_h",
)

_VALVE_FIELDS = (
    "name",
    "row_from",
    "row_to",
    "typed_q_m3h",
    "area_ha",
    "q_m3h",
)

_SCALE = {
    "row_spacing_m": 2,
    "tree_spacing_m": 2,
    "area_ha": 4,
    "emitter_spacing_m": 2,
    "emitter_flow_lph": 2,
    "flow_per_emitter_lph": 2,
    "typed_flow_m3h": 2,
    "typed_q_m3h": 2,
    "q_ha_m3h": 4,
    "q_block_m3h": 4,
    "rate_mm_h": 4,
}


def _jsonable(value: object) -> object:
    if isinstance(value, Decimal):
        return format(value, "f")
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


def _try_calc(fn: Callable[..., Any], *args: Any) -> Any:
    if any(arg is None for arg in args):
        return None
    try:
        return fn(*args)
    except CalcInputError:
        return None


def _load_plantings(db: Session, block_id: uuid.UUID) -> list[Planting]:
    return list(
        db.scalars(
            select(Planting)
            .where(Planting.block_id == block_id)
            .order_by(Planting.sort, Planting.id)
        ).all()
    )


def _load_layout(db: Session, block_id: uuid.UUID) -> IrrigationLayout | None:
    return db.scalar(select(IrrigationLayout).where(IrrigationLayout.block_id == block_id))


def _load_valves(db: Session, block_id: uuid.UUID) -> list[Valve]:
    return list(
        db.scalars(
            select(Valve).where(Valve.block_id == block_id).order_by(Valve.sort, Valve.id)
        ).all()
    )


def _effective_area(planting: Planting, block: Block, count: int) -> Decimal | None:
    if planting.area_ha is not None:
        return planting.area_ha
    if count == 1:
        return block.net_area_ha
    return None


def _planting_inputs(planting: Planting, area: Decimal | None) -> dict[str, object]:
    mode = planting.density_input
    payload: dict[str, object] = {"density_input": None if mode is None else mode.value}
    if mode == DensityInput.spacing:
        payload["row_spacing_m"] = planting.row_spacing_m
        payload["tree_spacing_m"] = planting.tree_spacing_m
    elif mode == DensityInput.density:
        payload["row_spacing_m"] = planting.row_spacing_m
        payload["trees_per_ha"] = planting.trees_per_ha
    elif mode == DensityInput.count:
        payload["trees_count"] = planting.trees_count
        payload["row_spacing_m"] = planting.row_spacing_m
    else:
        payload["row_spacing_m"] = planting.row_spacing_m
        payload["tree_spacing_m"] = planting.tree_spacing_m
        payload["trees_per_ha"] = planting.trees_per_ha
        payload["trees_count"] = planting.trees_count
    payload["area_ha"] = area
    return payload


def _recompute_planting(planting: Planting, block: Block, count: int) -> None:
    area = _effective_area(planting, block, count)
    mode = planting.density_input
    row_spacing_m = planting.row_spacing_m
    tree_spacing_m = planting.tree_spacing_m
    trees_per_ha = planting.trees_per_ha
    trees_count = planting.trees_count
    if mode == DensityInput.spacing:
        trees_per_ha = _try_calc(calc.trees_per_ha_from_spacing, row_spacing_m, tree_spacing_m)
        trees_count = _try_calc(calc.trees_in_block, trees_per_ha, area)
    elif mode == DensityInput.density:
        tree_spacing_m = _try_calc(calc.tree_spacing_from_density, row_spacing_m, trees_per_ha)
        trees_count = _try_calc(calc.trees_in_block, trees_per_ha, area)
    elif mode == DensityInput.count:
        trees_per_ha = _try_calc(calc.trees_per_ha_from_count, trees_count, area)
        tree_spacing_m = _try_calc(calc.tree_spacing_from_density, row_spacing_m, trees_per_ha)
    planting.trees_per_ha = trees_per_ha
    planting.tree_spacing_m = tree_spacing_m
    planting.trees_count = trees_count
    planting.inputs_hash = _inputs_hash(_planting_inputs(planting, area))
    planting.updated_at = datetime.now(UTC)


def _areas_flow(q_ha_m3h: Decimal | None, areas: list[Decimal | None]) -> Decimal | None:
    if q_ha_m3h is None or not areas or any(area is None for area in areas):
        return None
    pairs = [(q_ha_m3h, area) for area in areas if area is not None]
    return _try_calc(calc.q_block_m3h, pairs)


def _typed_layout_flow(
    layout: IrrigationLayout,
    block: Block,
    valves: list[Valve],
    inputs: dict[str, object],
) -> tuple[Decimal | None, Decimal | None]:
    basis = layout.typed_flow_basis
    inputs["typed_flow_m3h"] = layout.typed_flow_m3h
    inputs["typed_flow_basis"] = None if basis is None else basis.value
    if basis == TypedFlowBasis.block:
        q_block_m3h = _try_calc(calc.q_block_from_typed_m3h, layout.typed_flow_m3h, "block")
        q_ha_m3h = _try_calc(calc.q_ha_from_block_m3h, q_block_m3h, block.net_area_ha)
        return q_ha_m3h, q_block_m3h
    if basis == TypedFlowBasis.ha:
        flow = layout.typed_flow_m3h
        if flow is None or flow <= 0:
            return None, None
        if block.net_area_ha is None:
            return flow, None
        return flow, _try_calc(calc.q_block_from_typed_m3h, flow, "ha", block.net_area_ha)
    if basis == TypedFlowBasis.valve:
        flows = [valve.typed_q_m3h for valve in valves]
        inputs["valve_flows_m3h"] = flows
        if not flows or any(flow is None for flow in flows):
            return None, None
        present = [flow for flow in flows if flow is not None]
        try:
            q_block_m3h = calc.q_block_from_typed_m3h(Decimal("1"), "valve", None, present)
        except CalcInputError:
            return None, None
        q_ha_m3h = _try_calc(calc.q_ha_from_block_m3h, q_block_m3h, block.net_area_ha)
        return q_ha_m3h, q_block_m3h
    return None, None


def _layout_flows(
    layout: IrrigationLayout,
    block: Block,
    plantings: list[Planting],
    valves: list[Valve],
) -> tuple[Decimal | None, Decimal | None, dict[str, object]]:
    first = plantings[0] if plantings else None
    areas = [_effective_area(planting, block, len(plantings)) for planting in plantings]
    inputs: dict[str, object] = {
        "entry_mode": layout.entry_mode.value,
        "net_area_ha": block.net_area_ha,
    }
    if layout.entry_mode == FlowEntryMode.layout:
        row_spacing_m = None if first is None else first.row_spacing_m
        inputs["row_spacing_m"] = row_spacing_m
        inputs["laterals_per_row"] = layout.laterals_per_row
        inputs["emitter_spacing_m"] = layout.emitter_spacing_m
        inputs["emitter_flow_lph"] = layout.emitter_flow_lph
        inputs["areas_ha"] = areas
        q_ha_m3h = _try_calc(
            calc.q_ha_from_layout_m3h,
            row_spacing_m,
            layout.laterals_per_row,
            layout.emitter_spacing_m,
            layout.emitter_flow_lph,
        )
        return q_ha_m3h, _areas_flow(q_ha_m3h, areas), inputs
    if layout.entry_mode == FlowEntryMode.per_tree:
        trees_per_ha = None if first is None else first.trees_per_ha
        inputs["trees_per_ha"] = trees_per_ha
        inputs["emitters_per_tree"] = layout.emitters_per_tree
        inputs["flow_per_emitter_lph"] = layout.flow_per_emitter_lph
        inputs["areas_ha"] = areas
        q_ha_m3h = _try_calc(
            calc.q_ha_from_trees_m3h,
            trees_per_ha,
            layout.emitters_per_tree,
            layout.flow_per_emitter_lph,
        )
        return q_ha_m3h, _areas_flow(q_ha_m3h, areas), inputs
    q_ha_m3h, q_block_m3h = _typed_layout_flow(layout, block, valves, inputs)
    return q_ha_m3h, q_block_m3h, inputs


def _ensure_default_valve(db: Session, block: Block) -> None:
    if block.rows_total is None or block.rows_total < 1:
        return
    exists = db.scalar(select(Valve.id).where(Valve.block_id == block.id).limit(1))
    if exists is not None:
        return
    db.add(
        Valve(
            farm_id=block.farm_id,
            block_id=block.id,
            name="V1",
            sort=0,
            row_from=1,
            row_to=block.rows_total,
            updated_at=datetime.now(UTC),
        )
    )
    db.flush()


def _recompute_valve(valve: Valve, block: Block, q_block_m3h: Decimal | None) -> None:
    rows = _try_calc(calc.valve_rows, valve.row_from, valve.row_to, block.rows_total)
    area_ha = _try_calc(calc.valve_area_ha, block.net_area_ha, rows, block.rows_total)
    q_m3h = _try_calc(calc.valve_q_m3h, q_block_m3h, rows, block.rows_total)
    valve.area_ha = area_ha
    valve.q_m3h = q_m3h
    valve.inputs_hash = _inputs_hash(
        {
            "row_from": valve.row_from,
            "row_to": valve.row_to,
            "rows_total": block.rows_total,
            "net_area_ha": block.net_area_ha,
            "q_block_m3h": q_block_m3h,
        }
    )
    valve.updated_at = datetime.now(UTC)


def recompute_block(db: Session, block_id: uuid.UUID) -> None:
    """Recompute planting, layout, and valve totals for one block.

    Missing inputs leave the derived values null. A block with rows and no
    valves receives a default valve covering every row.
    """
    block = db.get(Block, block_id)
    if block is None:
        return
    plantings = _load_plantings(db, block.id)
    for planting in plantings:
        _recompute_planting(planting, block, len(plantings))
    _ensure_default_valve(db, block)
    valves = _load_valves(db, block.id)
    layout = _load_layout(db, block.id)
    q_block_m3h: Decimal | None = None
    if layout is not None:
        q_ha_m3h, q_block_m3h, inputs = _layout_flows(layout, block, plantings, valves)
        layout.q_ha_m3h = q_ha_m3h
        layout.q_block_m3h = q_block_m3h
        layout.rate_mm_h = _try_calc(calc.rate_mm_h, q_block_m3h, block.net_area_ha)
        layout.inputs_hash = _inputs_hash(inputs)
        layout.updated_at = datetime.now(UTC)
    for valve in valves:
        _recompute_valve(valve, block, q_block_m3h)


def _row_dict(row: object, fields: tuple[str, ...]) -> dict[str, object]:
    return {field: getattr(row, field) for field in fields}


def _registry_snapshot(db: Session, block_id: uuid.UUID) -> dict[str, Any]:
    layout = _load_layout(db, block_id)
    return {
        "plantings": [_row_dict(row, _PLANTING_FIELDS) for row in _load_plantings(db, block_id)],
        "layout": None if layout is None else _row_dict(layout, _LAYOUT_FIELDS),
        "valves": [_row_dict(row, _VALVE_FIELDS) for row in _load_valves(db, block_id)],
    }


def _same_value(field: str, left: object, right: object) -> bool:
    if isinstance(left, Decimal) or isinstance(right, Decimal):
        if not isinstance(left, Decimal) or not isinstance(right, Decimal):
            return False
        places = _SCALE.get(field)
        if places is None:
            return left == right
        quantum = Decimal(1).scaleb(-places)
        return left.quantize(quantum, rounding=ROUND_HALF_UP) == right.quantize(
            quantum, rounding=ROUND_HALF_UP
        )
    return left == right


def _diff_rows(
    prefix: str,
    before: list[dict[str, object]],
    after: list[dict[str, object]],
    fields: tuple[str, ...],
) -> list[str]:
    changed: list[str] = []
    width = max(len(before), len(after))
    for field in fields:
        for index in range(width):
            old = before[index].get(field) if index < len(before) else None
            new = after[index].get(field) if index < len(after) else None
            if not _same_value(field, old, new):
                changed.append(f"{prefix}.{field}")
                break
    return changed


def _registry_changes(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    changed = _diff_rows("planting", before["plantings"], after["plantings"], _PLANTING_FIELDS)
    layout_before = before["layout"] or {}
    layout_after = after["layout"] or {}
    if before["layout"] is not None or after["layout"] is not None:
        for field in _LAYOUT_FIELDS:
            if not _same_value(field, layout_before.get(field), layout_after.get(field)):
                changed.append(f"irrigation_layout.{field}")
    changed.extend(_diff_rows("valve", before["valves"], after["valves"], _VALVE_FIELDS))
    return changed


def _begin_subwrite(block: Block, if_match: str | None, reason: str | None) -> None:
    _require_if_match(block, if_match)
    if block.status == BlockStatus.complete and _clean_reason(reason) is None:
        raise AppError("validation_error", 422, {"reason": "record.reason_required"})


def _finish_block_write(
    db: Session,
    block: Block,
    user: AppUser,
    changed: list[str],
    reason: str | None,
) -> Block:
    block.version += 1
    block.updated_at = datetime.now(UTC)
    _add_history(db, block, user, changed, _clean_reason(reason))
    _commit(db)
    db.refresh(block)
    return block


def _delete_rows(db: Session, rows: list[Any]) -> None:
    for row in rows:
        db.delete(row)
    db.flush()


def _variety_errors(db: Session, plantings: list[PlantingIn]) -> dict[str, str]:
    wanted = {item.variety_id for item in plantings if item.variety_id is not None}
    found: set[uuid.UUID] = set()
    if wanted:
        found = set(db.scalars(select(Variety.id).where(Variety.id.in_(wanted))).all())
    errors: dict[str, str] = {}
    for index, item in enumerate(plantings):
        if item.variety_id is not None and item.variety_id not in found:
            errors[f"plantings.{index}.variety_id"] = "catalog.variety_not_found"
    return errors


def _valve_row_errors(valves: list[ValveWrite], rows_total: int | None) -> dict[str, str]:
    errors: dict[str, str] = {}
    if rows_total is None or rows_total < 1:
        for index, _valve in enumerate(valves):
            errors[f"valves.{index}.row_from"] = "registry.valve_rows_invalid"
        return errors
    spans: list[tuple[int, int, int]] = []
    for index, valve in enumerate(valves):
        try:
            calc.valve_rows(valve.row_from, valve.row_to, rows_total)
        except CalcInputError:
            errors[f"valves.{index}.row_from"] = "registry.valve_rows_invalid"
            continue
        spans.append((index, valve.row_from, valve.row_to))
    spans.sort(key=lambda item: (item[1], item[2], item[0]))
    previous_end = 0
    for index, start, end in spans:
        if start <= previous_end:
            errors[f"valves.{index}.row_from"] = "registry.valve_rows_overlap"
        if end > previous_end:
            previous_end = end
    return errors


def _positive_decimal(value: Decimal | None) -> bool:
    return isinstance(value, Decimal) and value.is_finite() and value > 0


def _positive_int(value: int | None) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _planting_ready(plantings: list[Planting], block: Block) -> bool:
    if not plantings:
        return False
    planting = plantings[0]
    if planting.density_input == DensityInput.spacing:
        return _positive_decimal(planting.row_spacing_m) and _positive_decimal(
            planting.tree_spacing_m
        )
    if planting.density_input == DensityInput.density:
        return _positive_decimal(planting.row_spacing_m) and _positive_int(planting.trees_per_ha)
    if planting.density_input == DensityInput.count:
        area = _effective_area(planting, block, len(plantings))
        return _positive_int(planting.trees_count) and _positive_decimal(area)
    return False


def _layout_ready(layout: IrrigationLayout | None, valves: list[Valve]) -> str | None:
    if layout is None or layout.entry_mode == FlowEntryMode.layout:
        ready = (
            layout is not None
            and _positive_int(layout.laterals_per_row)
            and _positive_decimal(layout.emitter_spacing_m)
            and _positive_decimal(layout.emitter_flow_lph)
        )
        if ready:
            return None
        return "irrigation.layout_incomplete"
    if layout.entry_mode == FlowEntryMode.typed_flow:
        if layout.typed_flow_basis == TypedFlowBasis.valve:
            if valves and all(_positive_decimal(valve.typed_q_m3h) for valve in valves):
                return None
            return "irrigation.typed_flow_required"
        if layout.typed_flow_basis in (
            TypedFlowBasis.block,
            TypedFlowBasis.ha,
        ) and _positive_decimal(layout.typed_flow_m3h):
            return None
        return "irrigation.typed_flow_required"
    return None


def _complete_errors(db: Session, block: Block) -> dict[str, str]:
    errors: dict[str, str] = {}
    has_outline = db.scalar(select(Block.outline.is_not(None)).where(Block.id == block.id))
    if has_outline is not True:
        errors["outline"] = "block.outline_required"
    if not _positive_decimal(block.net_area_ha):
        errors["net_area_ha"] = "block.net_area_required"
    if block.crop_id is None:
        errors["crop_id"] = "block.crop_required"
    if not _planting_ready(_load_plantings(db, block.id), block):
        errors["planting"] = "planting.spacing_required"
    layout_code = _layout_ready(_load_layout(db, block.id), _load_valves(db, block.id))
    if layout_code is not None:
        errors["irrigation_layout"] = layout_code
    if not _positive_int(block.rows_total):
        errors["rows_total"] = "block.rows_required"
    return errors


def create_block(db: Session, farm: Farm, body: BlockCreate) -> Block:
    net_area_ha = _quantize_area(body.net_area_ha)
    errors = _field_errors(
        db,
        farm_id=farm.id,
        block_id=None,
        name=body.name,
        status=BlockStatus.draft,
        reason=None,
        crop_id=body.crop_id,
        training_system_id=body.training_system_id,
        net_area_ha=net_area_ha,
        outline=body.outline,
        row_line=body.row_line,
        outline_provided=body.outline is not None,
        row_line_provided=body.row_line is not None,
        has_outline=False,
        has_row_line=False,
        current_area_ha=None,
    )
    if errors:
        raise AppError("validation_error", 422, errors)

    block = Block(
        farm_id=farm.id,
        name=body.name,
        status=BlockStatus.draft,
        net_area_ha=net_area_ha,
        rows_total=body.rows_total,
        crop_id=body.crop_id,
        training_system_id=body.training_system_id,
        training_other=body.training_other,
        version=1,
        updated_at=datetime.now(UTC),
    )
    if body.outline is not None:
        block.outline = _from_geojson(body.outline)
    if body.row_line is not None:
        block.row_line = _from_geojson(body.row_line)
    db.add(block)
    _write_calculated(db, block)
    recompute_block(db, block.id)
    _commit(db)
    db.refresh(block)
    return block


def update_block(
    db: Session,
    block: Block,
    user: AppUser,
    body: BlockUpdate,
    if_match: str | None,
) -> Block:
    _require_if_match(block, if_match)
    provided = body.model_fields_set
    name = body.name if "name" in provided else block.name
    net_area_ha = (
        _quantize_area(body.net_area_ha)
        if "net_area_ha" in provided
        else _quantize_area(block.net_area_ha)
    )
    crop_id = body.crop_id if "crop_id" in provided else block.crop_id
    training_system_id = (
        body.training_system_id if "training_system_id" in provided else block.training_system_id
    )
    training_other = body.training_other if "training_other" in provided else block.training_other
    rows_total = body.rows_total if "rows_total" in provided else block.rows_total
    reason = body.reason if "reason" in provided else None
    outline = body.outline if "outline" in provided else None
    row_line = body.row_line if "row_line" in provided else None
    errors = _field_errors(
        db,
        farm_id=block.farm_id,
        block_id=block.id,
        name=name,
        status=block.status,
        reason=reason,
        crop_id=crop_id,
        training_system_id=training_system_id,
        net_area_ha=net_area_ha,
        outline=outline,
        row_line=row_line,
        outline_provided="outline" in provided,
        row_line_provided="row_line" in provided,
        has_outline=block.outline is not None,
        has_row_line=block.row_line is not None,
        current_area_ha=block.gross_area_ha,
    )
    if errors:
        raise AppError("validation_error", 422, errors)

    children_before = None
    if net_area_ha != _quantize_area(block.net_area_ha) or rows_total != block.rows_total:
        children_before = _registry_snapshot(db, block.id)
    before = _snapshot(block)
    outline_changed = (
        _geometry_changed(db, Block.outline, block.id, outline) if "outline" in provided else False
    )
    row_line_changed = (
        _geometry_changed(db, Block.row_line, block.id, row_line)
        if "row_line" in provided
        else False
    )
    block.name = _require_name(name)
    block.net_area_ha = net_area_ha
    block.crop_id = crop_id
    block.training_system_id = training_system_id
    block.training_other = training_other
    block.rows_total = rows_total
    if "outline" in provided:
        block.outline = None if outline is None else _from_geojson(outline)
    if "row_line" in provided:
        block.row_line = None if row_line is None else _from_geojson(row_line)
    block.updated_at = datetime.now(UTC)
    gross_area_ha, row_bearing_deg = _write_calculated(db, block)
    changed = _changed_fields(
        before,
        block,
        gross_area_ha,
        row_bearing_deg,
        outline_changed=outline_changed,
        row_line_changed=row_line_changed,
    )
    if children_before is not None:
        recompute_block(db, block.id)
        changed.extend(_registry_changes(children_before, _registry_snapshot(db, block.id)))
    block.version += 1
    _add_history(db, block, user, changed, _clean_reason(reason))
    _commit(db)
    db.refresh(block)
    return block


def archive_block(
    db: Session,
    block: Block,
    user: AppUser,
    if_match: str | None,
    reason: str | None,
) -> Block:
    _require_if_match(block, if_match)
    cleaned = _clean_reason(reason)
    if block.status == BlockStatus.complete and cleaned is None:
        raise AppError("validation_error", 422, {"reason": "record.reason_required"})
    before = _snapshot(block)
    block.status = BlockStatus.archived
    block.updated_at = datetime.now(UTC)
    gross_area_ha, row_bearing_deg = _write_calculated(db, block)
    changed = _changed_fields(
        before,
        block,
        gross_area_ha,
        row_bearing_deg,
        outline_changed=False,
        row_line_changed=False,
    )
    block.version += 1
    _add_history(db, block, user, changed, cleaned)
    _commit(db)
    db.refresh(block)
    return block


def _crop_out(crop: Crop | None) -> BlockCropOut | None:
    if crop is None:
        return None
    return BlockCropOut(
        id=crop.id,
        code=crop.code,
        name=LocalizedName(fr=crop.name_fr, ar=crop.name_ar, en=crop.name_en),
    )


def _crops_by_id(db: Session, blocks: list[Block]) -> dict[uuid.UUID, Crop]:
    crop_ids = {block.crop_id for block in blocks if block.crop_id is not None}
    if not crop_ids:
        return {}
    rows = db.scalars(select(Crop).where(Crop.id.in_(crop_ids))).all()
    return {row.id: row for row in rows}


def _load_geojson(value: object) -> dict[str, Any] | None:
    if not isinstance(value, str):
        return None
    loaded = json.loads(value)
    if isinstance(loaded, dict):
        return loaded
    return None


def _geojson_pair(
    db: Session, block_id: uuid.UUID
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    outline, row_line = db.execute(
        select(func.ST_AsGeoJSON(Block.outline), func.ST_AsGeoJSON(Block.row_line)).where(
            Block.id == block_id
        )
    ).one()
    return _load_geojson(outline), _load_geojson(row_line)


def _label_entered(value: object) -> SourceLabel | None:
    if value is None:
        return None
    return "entered"


def _label_calculated(value: object) -> SourceLabel | None:
    if value is None:
        return None
    return "calculated"


def _area_defaulted(planting: Planting, block: Block, count: int) -> bool:
    return planting.area_ha is None and count == 1 and block.net_area_ha is not None


def _planting_sources(planting: Planting, area_defaulted: bool) -> PlantingSources:
    area_source: SourceLabel | None = (
        "calculated" if area_defaulted else _label_entered(planting.area_ha)
    )
    if planting.density_input == DensityInput.spacing:
        return PlantingSources(
            row_spacing_m=_label_entered(planting.row_spacing_m),
            tree_spacing_m=_label_entered(planting.tree_spacing_m),
            trees_per_ha=_label_calculated(planting.trees_per_ha),
            trees_count=_label_calculated(planting.trees_count),
            area_ha=area_source,
        )
    if planting.density_input == DensityInput.density:
        return PlantingSources(
            row_spacing_m=_label_entered(planting.row_spacing_m),
            trees_per_ha=_label_entered(planting.trees_per_ha),
            tree_spacing_m=_label_calculated(planting.tree_spacing_m),
            trees_count=_label_calculated(planting.trees_count),
            area_ha=area_source,
        )
    if planting.density_input == DensityInput.count:
        return PlantingSources(
            trees_count=_label_entered(planting.trees_count),
            row_spacing_m=_label_entered(planting.row_spacing_m),
            trees_per_ha=_label_calculated(planting.trees_per_ha),
            tree_spacing_m=_label_calculated(planting.tree_spacing_m),
            area_ha=area_source,
        )
    return PlantingSources(
        row_spacing_m=_label_entered(planting.row_spacing_m),
        tree_spacing_m=_label_entered(planting.tree_spacing_m),
        trees_per_ha=_label_entered(planting.trees_per_ha),
        trees_count=_label_entered(planting.trees_count),
        area_ha=area_source,
    )


def _planting_out(planting: Planting, block: Block, count: int) -> PlantingOut:
    defaulted = _area_defaulted(planting, block, count)
    return PlantingOut(
        id=planting.id,
        variety_id=planting.variety_id,
        variety_text=planting.variety_text,
        rootstock=planting.rootstock,
        planting_year=planting.planting_year,
        density_input=planting.density_input,
        row_spacing_m=planting.row_spacing_m,
        tree_spacing_m=planting.tree_spacing_m,
        trees_per_ha=planting.trees_per_ha,
        trees_count=planting.trees_count,
        area_ha=_effective_area(planting, block, count),
        sort=planting.sort,
        sources=_planting_sources(planting, defaulted),
    )


def _layout_out(layout: IrrigationLayout) -> IrrigationLayoutOut:
    return IrrigationLayoutOut(
        id=layout.id,
        system=layout.system,
        entry_mode=layout.entry_mode,
        laterals_per_row=layout.laterals_per_row,
        emitter_spacing_m=layout.emitter_spacing_m,
        emitter_flow_lph=layout.emitter_flow_lph,
        emitters_per_tree=layout.emitters_per_tree,
        flow_per_emitter_lph=layout.flow_per_emitter_lph,
        typed_flow_m3h=layout.typed_flow_m3h,
        typed_flow_basis=layout.typed_flow_basis,
        flow_meter=layout.flow_meter,
        q_ha_m3h=layout.q_ha_m3h,
        q_block_m3h=layout.q_block_m3h,
        rate_mm_h=layout.rate_mm_h,
        sources=IrrigationLayoutSources(
            laterals_per_row=_label_entered(layout.laterals_per_row),
            emitter_spacing_m=_label_entered(layout.emitter_spacing_m),
            emitter_flow_lph=_label_entered(layout.emitter_flow_lph),
            emitters_per_tree=_label_entered(layout.emitters_per_tree),
            flow_per_emitter_lph=_label_entered(layout.flow_per_emitter_lph),
            typed_flow_m3h=_label_entered(layout.typed_flow_m3h),
            typed_flow_basis=_label_entered(layout.typed_flow_basis),
            q_ha_m3h=_label_calculated(layout.q_ha_m3h),
            q_block_m3h=_label_calculated(layout.q_block_m3h),
            rate_mm_h=_label_calculated(layout.rate_mm_h),
        ),
    )


def _valve_out(valve: Valve) -> BlockValveOut:
    return BlockValveOut(
        id=valve.id,
        name=valve.name,
        sort=valve.sort,
        row_from=valve.row_from,
        row_to=valve.row_to,
        typed_q_m3h=valve.typed_q_m3h,
        area_ha=valve.area_ha,
        q_m3h=valve.q_m3h,
        sources=ValveSources(
            typed_q_m3h=_label_entered(valve.typed_q_m3h),
            area_ha=_label_calculated(valve.area_ha),
            q_m3h=_label_calculated(valve.q_m3h),
        ),
    )


def _sum_trees(plantings: list[Planting]) -> int | None:
    counts = [planting.trees_count for planting in plantings if planting.trees_count is not None]
    if not counts:
        return None
    return sum(counts)


def _list_totals(
    db: Session, block_ids: set[uuid.UUID]
) -> tuple[dict[uuid.UUID, int | None], dict[uuid.UUID, IrrigationLayout]]:
    if not block_ids:
        return {}, {}
    grouped: dict[uuid.UUID, list[Planting]] = {}
    for planting in db.scalars(select(Planting).where(Planting.block_id.in_(block_ids))).all():
        grouped.setdefault(planting.block_id, []).append(planting)
    layouts = {
        layout.block_id: layout
        for layout in db.scalars(
            select(IrrigationLayout).where(IrrigationLayout.block_id.in_(block_ids))
        ).all()
    }
    trees = {block_id: _sum_trees(rows) for block_id, rows in grouped.items()}
    return trees, layouts


def replace_plantings(
    db: Session,
    block: Block,
    user: AppUser,
    body: PlantingsPut,
    if_match: str | None,
) -> Block:
    _begin_subwrite(block, if_match, body.reason)
    errors = _variety_errors(db, body.plantings)
    if errors:
        raise AppError("validation_error", 422, errors)
    before = _registry_snapshot(db, block.id)
    _delete_rows(db, _load_plantings(db, block.id))
    now = datetime.now(UTC)
    for index, item in enumerate(body.plantings):
        db.add(
            Planting(
                farm_id=block.farm_id,
                block_id=block.id,
                variety_id=item.variety_id,
                variety_text=item.variety_text,
                rootstock=item.rootstock,
                planting_year=item.planting_year,
                density_input=item.density_input,
                row_spacing_m=item.row_spacing_m,
                tree_spacing_m=item.tree_spacing_m,
                trees_per_ha=item.trees_per_ha,
                trees_count=item.trees_count,
                area_ha=item.area_ha,
                sort=index,
                updated_at=now,
            )
        )
    db.flush()
    recompute_block(db, block.id)
    changed = _registry_changes(before, _registry_snapshot(db, block.id))
    return _finish_block_write(db, block, user, changed, body.reason)


def replace_irrigation_layout(
    db: Session,
    block: Block,
    user: AppUser,
    body: IrrigationLayoutPut,
    if_match: str | None,
) -> Block:
    _begin_subwrite(block, if_match, body.reason)
    before = _registry_snapshot(db, block.id)
    layout = _load_layout(db, block.id)
    now = datetime.now(UTC)
    if layout is None:
        layout = IrrigationLayout(
            farm_id=block.farm_id,
            block_id=block.id,
            system=body.system,
            entry_mode=body.entry_mode,
            updated_at=now,
        )
        db.add(layout)
    layout.system = body.system
    layout.entry_mode = body.entry_mode
    layout.laterals_per_row = body.laterals_per_row
    layout.emitter_spacing_m = body.emitter_spacing_m
    layout.emitter_flow_lph = body.emitter_flow_lph
    layout.emitters_per_tree = body.emitters_per_tree
    layout.flow_per_emitter_lph = body.flow_per_emitter_lph
    layout.typed_flow_m3h = body.typed_flow_m3h
    layout.typed_flow_basis = body.typed_flow_basis
    layout.flow_meter = body.flow_meter
    layout.updated_at = now
    db.flush()
    recompute_block(db, block.id)
    changed = _registry_changes(before, _registry_snapshot(db, block.id))
    return _finish_block_write(db, block, user, changed, body.reason)


def replace_valves(
    db: Session,
    block: Block,
    user: AppUser,
    body: ValvesPut,
    if_match: str | None,
) -> Block:
    _begin_subwrite(block, if_match, body.reason)
    errors = _valve_row_errors(body.valves, block.rows_total)
    if errors:
        raise AppError("validation_error", 422, errors)
    before = _registry_snapshot(db, block.id)
    _delete_rows(db, _load_valves(db, block.id))
    now = datetime.now(UTC)
    for index, item in enumerate(body.valves):
        db.add(
            Valve(
                farm_id=block.farm_id,
                block_id=block.id,
                name=item.name,
                sort=index,
                row_from=item.row_from,
                row_to=item.row_to,
                typed_q_m3h=item.typed_q_m3h,
                updated_at=now,
            )
        )
    db.flush()
    recompute_block(db, block.id)
    changed = _registry_changes(before, _registry_snapshot(db, block.id))
    return _finish_block_write(db, block, user, changed, body.reason)


def complete_block(
    db: Session,
    block: Block,
    user: AppUser,
    if_match: str | None,
) -> Block:
    _require_if_match(block, if_match)
    errors = _complete_errors(db, block)
    if errors:
        raise AppError("block.incomplete", 422, errors)
    if block.status == BlockStatus.complete:
        return block
    block.status = BlockStatus.complete
    block.updated_at = datetime.now(UTC)
    block.version += 1
    _add_history(db, block, user, ["status"], "completed")
    _commit(db)
    db.refresh(block)
    return block


def to_block_out(db: Session, block: Block) -> BlockOut:
    outline, row_line = _geojson_pair(db, block.id)
    crop = db.get(Crop, block.crop_id) if block.crop_id is not None else None
    plantings = _load_plantings(db, block.id)
    layout = _load_layout(db, block.id)
    valves = _load_valves(db, block.id)
    return BlockOut(
        id=block.id,
        name=block.name,
        status=block.status,
        version=block.version,
        crop=_crop_out(crop),
        gross_area_ha=format_area_ha(block.gross_area_ha),
        net_area_ha=format_area_ha(block.net_area_ha),
        trees_count=_sum_trees(plantings),
        q_block_m3h=None if layout is None else format_flow_m3h(layout.q_block_m3h),
        rate_mm_h=None if layout is None else format_rate_mm_h(layout.rate_mm_h),
        outline=outline,
        row_line=row_line,
        row_bearing_deg=format_bearing_deg(block.row_bearing_deg),
        rows_total=block.rows_total,
        training_system_id=block.training_system_id,
        training_other=block.training_other,
        sources=BlockSources(),
        plantings=[_planting_out(planting, block, len(plantings)) for planting in plantings],
        irrigation_layout=None if layout is None else _layout_out(layout),
        valves=[_valve_out(valve) for valve in valves],
    )


def _outlines_by_id(
    db: Session, block_ids: set[uuid.UUID]
) -> dict[uuid.UUID, dict[str, Any] | None]:
    if not block_ids:
        return {}
    rows = db.execute(
        select(Block.id, func.ST_AsGeoJSON(Block.outline)).where(Block.id.in_(block_ids))
    ).all()
    return {block_id: _load_geojson(geojson) for block_id, geojson in rows}


def list_blocks(db: Session, farm: Farm, *, include_archived: bool) -> list[BlockListItem]:
    stmt = select(Block).where(Block.farm_id == farm.id)
    if not include_archived:
        stmt = stmt.where(Block.status != BlockStatus.archived)
    rows = list(db.scalars(stmt.order_by(Block.name)).all())
    crops = _crops_by_id(db, rows)
    block_ids = {row.id for row in rows}
    trees, layouts = _list_totals(db, block_ids)
    outlines = _outlines_by_id(db, block_ids)
    items: list[BlockListItem] = []
    for row in rows:
        layout = layouts.get(row.id)
        items.append(
            BlockListItem(
                id=row.id,
                name=row.name,
                status=row.status,
                crop=_crop_out(crops.get(row.crop_id)) if row.crop_id is not None else None,
                gross_area_ha=format_area_ha(row.gross_area_ha),
                net_area_ha=format_area_ha(row.net_area_ha),
                trees_count=trees.get(row.id),
                q_block_m3h=None if layout is None else format_flow_m3h(layout.q_block_m3h),
                rate_mm_h=None if layout is None else format_rate_mm_h(layout.rate_mm_h),
                outline=outlines.get(row.id),
                version=row.version,
            )
        )
    return items


def list_history(db: Session, block: Block) -> list[BlockHistoryOut]:
    rows = db.scalars(
        select(RecordVersion)
        .where(
            RecordVersion.farm_id == block.farm_id,
            RecordVersion.entity_type == _BLOCK_ENTITY,
            RecordVersion.entity_id == block.id,
        )
        .order_by(RecordVersion.changed_at.desc(), RecordVersion.version.desc())
    ).all()
    return [
        BlockHistoryOut(
            id=row.id,
            entity_type=row.entity_type,
            entity_id=row.entity_id,
            version=row.version,
            changed_fields=list(row.changed_fields),
            reason=row.reason,
            user_id=row.user_id,
            changed_at=row.changed_at,
        )
        for row in rows
    ]
