from decimal import Decimal

from fastapi import APIRouter, Depends

from app.core.deps import Db
from app.core.errors import AppError
from app.core.security import get_current_user
from app.modules.registry.calc import (
    CalcInputError,
    emitters_per_ha,
    lateral_length_m_per_ha,
    q_block_from_typed_m3h,
    q_block_m3h,
    q_ha_from_block_m3h,
    q_ha_from_layout_m3h,
    q_ha_from_trees_m3h,
    rate_mm_h,
    row_length_m_per_ha,
    tree_spacing_from_density,
    trees_in_block,
    trees_per_ha_from_count,
    trees_per_ha_from_spacing,
    valve_area_ha,
    valve_q_m3h,
    valve_rows,
)
from app.modules.registry.schemas import (
    GeometryPreviewIn,
    GeometryPreviewOut,
    IrrigationPreviewIn,
    IrrigationPreviewOut,
    PlantingPreviewIn,
    PlantingPreviewOut,
    ValveOut,
)
from app.modules.registry.service import preview_geometry

router = APIRouter(
    prefix="/calc/registry",
    tags=["registry"],
    dependencies=[Depends(get_current_user)],
)


def _positive_code(field: str) -> str:
    return f"registry.{field}_must_be_positive"


def _reject_non_positive(value: Decimal | int | None, field: str) -> None:
    if value is None:
        return
    if isinstance(value, Decimal):
        if not value.is_finite() or value <= 0:
            raise CalcInputError(field, _positive_code(field))
        return
    if value <= 0:
        raise CalcInputError(field, _positive_code(field))


def _block_from_ha(q_ha_m3h: Decimal, net_area_ha: Decimal | None) -> Decimal | None:
    if net_area_ha is None:
        return None
    return q_block_m3h([(q_ha_m3h, net_area_ha)])


def _planting_result(body: PlantingPreviewIn) -> PlantingPreviewOut:
    trees_per_ha: int | None = None
    tree_spacing_m: Decimal | None = None
    trees_in_block_count: int | None = None
    _reject_non_positive(body.row_spacing_m, "row_spacing_m")
    _reject_non_positive(body.net_area_ha, "net_area_ha")

    if body.mode == "spacing":
        _reject_non_positive(body.tree_spacing_m, "tree_spacing_m")
        tree_spacing_m = body.tree_spacing_m
        if body.row_spacing_m is not None and body.tree_spacing_m is not None:
            trees_per_ha = trees_per_ha_from_spacing(body.row_spacing_m, body.tree_spacing_m)
    elif body.mode == "density":
        _reject_non_positive(body.trees_per_ha, "trees_per_ha")
        trees_per_ha = body.trees_per_ha
        if body.row_spacing_m is not None and body.trees_per_ha is not None:
            tree_spacing_m = tree_spacing_from_density(body.row_spacing_m, body.trees_per_ha)
    else:
        _reject_non_positive(body.trees_count, "trees_count")
        trees_in_block_count = body.trees_count
        if body.trees_count is not None and body.net_area_ha is not None:
            trees_per_ha = trees_per_ha_from_count(body.trees_count, body.net_area_ha)
        if body.row_spacing_m is not None and trees_per_ha is not None:
            tree_spacing_m = tree_spacing_from_density(body.row_spacing_m, trees_per_ha)

    if trees_in_block_count is None and trees_per_ha is not None and body.net_area_ha is not None:
        trees_in_block_count = trees_in_block(trees_per_ha, body.net_area_ha)

    return PlantingPreviewOut(
        trees_per_ha=trees_per_ha,
        tree_spacing_m=tree_spacing_m,
        trees_in_block=trees_in_block_count,
    )


def _layout_flows(body: IrrigationPreviewIn) -> tuple[Decimal | None, Decimal | None]:
    _reject_non_positive(body.row_spacing_m, "row_spacing_m")
    _reject_non_positive(body.laterals_per_row, "laterals_per_row")
    _reject_non_positive(body.emitter_spacing_m, "emitter_spacing_m")
    _reject_non_positive(body.emitter_flow_lph, "emitter_flow_lph")
    if (
        body.row_spacing_m is None
        or body.laterals_per_row is None
        or body.emitter_spacing_m is None
        or body.emitter_flow_lph is None
    ):
        return None, None
    q_ha = q_ha_from_layout_m3h(
        body.row_spacing_m,
        body.laterals_per_row,
        body.emitter_spacing_m,
        body.emitter_flow_lph,
    )
    return q_ha, _block_from_ha(q_ha, body.net_area_ha)


def _per_tree_flows(body: IrrigationPreviewIn) -> tuple[Decimal | None, Decimal | None]:
    _reject_non_positive(body.trees_per_ha, "trees_per_ha")
    _reject_non_positive(body.emitters_per_tree, "emitters_per_tree")
    _reject_non_positive(body.flow_per_emitter_lph, "flow_per_emitter_lph")
    if (
        body.trees_per_ha is None
        or body.emitters_per_tree is None
        or body.flow_per_emitter_lph is None
    ):
        return None, None
    q_ha = q_ha_from_trees_m3h(
        body.trees_per_ha,
        body.emitters_per_tree,
        body.flow_per_emitter_lph,
    )
    return q_ha, _block_from_ha(q_ha, body.net_area_ha)


def _valve_typed_flows(body: IrrigationPreviewIn) -> list[Decimal] | None:
    valves = body.valves or []
    if not valves:
        return None
    flows: list[Decimal] = []
    for valve in valves:
        if valve.typed_q_m3h is None:
            return None
        _reject_non_positive(valve.typed_q_m3h, "typed_q_m3h")
        flows.append(valve.typed_q_m3h)
    return flows


def _ha_from_block(q_block: Decimal, net_area_ha: Decimal | None) -> Decimal | None:
    if net_area_ha is None:
        return None
    return q_ha_from_block_m3h(q_block, net_area_ha)


def _typed_flows(body: IrrigationPreviewIn) -> tuple[Decimal | None, Decimal | None]:
    basis = body.typed_flow_basis
    if basis is None:
        return None, None
    if basis == "valve":
        flows = _valve_typed_flows(body)
        if not flows:
            return None, None
        q_block = q_block_from_typed_m3h(Decimal("1"), "valve", body.net_area_ha, flows)
        return _ha_from_block(q_block, body.net_area_ha), q_block
    _reject_non_positive(body.typed_flow_m3h, "typed_flow_m3h")
    if body.typed_flow_m3h is None:
        return None, None
    if basis == "block":
        q_block = q_block_from_typed_m3h(body.typed_flow_m3h, "block", body.net_area_ha)
        return _ha_from_block(q_block, body.net_area_ha), q_block
    if body.net_area_ha is None:
        return body.typed_flow_m3h, None
    q_block = q_block_from_typed_m3h(body.typed_flow_m3h, "ha", body.net_area_ha)
    return body.typed_flow_m3h, q_block


def _irrigation_flows(body: IrrigationPreviewIn) -> tuple[Decimal | None, Decimal | None]:
    _reject_non_positive(body.net_area_ha, "net_area_ha")
    if body.entry_mode == "layout":
        return _layout_flows(body)
    if body.entry_mode == "per_tree":
        return _per_tree_flows(body)
    return _typed_flows(body)


def _valve_outputs(body: IrrigationPreviewIn, block_flow_m3h: Decimal | None) -> list[ValveOut]:
    if not body.valves:
        return []
    outputs: list[ValveOut] = []
    for index, valve in enumerate(body.valves):
        rows: int | None = None
        area: Decimal | None = None
        flow: Decimal | None = None
        if body.rows_total is not None:
            try:
                rows = valve_rows(valve.row_from, valve.row_to, body.rows_total)
            except CalcInputError as exc:
                raise CalcInputError(f"valves.{index}.row_from", exc.code) from None
            if body.net_area_ha is not None:
                area = valve_area_ha(body.net_area_ha, rows, body.rows_total)
            if block_flow_m3h is not None:
                flow = valve_q_m3h(block_flow_m3h, rows, body.rows_total)
        outputs.append(
            ValveOut(
                row_from=valve.row_from,
                row_to=valve.row_to,
                rows=rows,
                area_ha=area,
                q_m3h=flow,
            )
        )
    if body.rows_total is not None:
        ordered = sorted(
            ((index, valve.row_from, valve.row_to) for index, valve in enumerate(body.valves)),
            key=lambda item: (item[1], item[2], item[0]),
        )
        previous_end = 0
        for index, start, end in ordered:
            if start <= previous_end:
                raise CalcInputError(f"valves.{index}.row_from", "registry.valve_rows_overlap")
            previous_end = end
    return outputs


def _layout_lengths(
    body: IrrigationPreviewIn,
) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
    if body.entry_mode != "layout" or body.row_spacing_m is None:
        return None, None, None
    row_m = row_length_m_per_ha(body.row_spacing_m)
    if body.laterals_per_row is None:
        return row_m, None, None
    lateral_m = lateral_length_m_per_ha(body.row_spacing_m, body.laterals_per_row)
    if body.emitter_spacing_m is None:
        return row_m, lateral_m, None
    return (
        row_m,
        lateral_m,
        emitters_per_ha(body.row_spacing_m, body.laterals_per_row, body.emitter_spacing_m),
    )


def _irrigation_result(body: IrrigationPreviewIn) -> IrrigationPreviewOut:
    q_ha, q_block = _irrigation_flows(body)
    rate = (
        rate_mm_h(q_block, body.net_area_ha)
        if q_block is not None and body.net_area_ha is not None
        else None
    )
    row_m, lateral_m, emitters = _layout_lengths(body)
    return IrrigationPreviewOut(
        q_ha_m3h=q_ha,
        q_block_m3h=q_block,
        rate_mm_h=rate,
        row_m_per_ha=row_m,
        lateral_m_per_ha=lateral_m,
        emitters_per_ha=emitters,
        valves=_valve_outputs(body, q_block),
    )


@router.post("/geometry", response_model=GeometryPreviewOut)
def preview_block_geometry(body: GeometryPreviewIn, db: Db) -> GeometryPreviewOut:
    gross_area_ha, row_bearing_deg = preview_geometry(db, body.outline, body.row_line)
    return GeometryPreviewOut(gross_area_ha=gross_area_ha, row_bearing_deg=row_bearing_deg)


@router.post("/planting", response_model=PlantingPreviewOut)
def preview_planting(body: PlantingPreviewIn) -> PlantingPreviewOut:
    try:
        return _planting_result(body)
    except CalcInputError as exc:
        raise AppError("validation_error", 422, {exc.field: exc.code}) from None


@router.post("/irrigation", response_model=IrrigationPreviewOut)
def preview_irrigation(body: IrrigationPreviewIn) -> IrrigationPreviewOut:
    try:
        return _irrigation_result(body)
    except CalcInputError as exc:
        raise AppError("validation_error", 422, {exc.field: exc.code}) from None
