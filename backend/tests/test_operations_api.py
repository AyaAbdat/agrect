"""Operations API: product totals, valve area, PHI warning, re-entry, scoping."""

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.auth.models import AppUser
from app.modules.catalog.loader import load_catalog
from app.modules.farms.models import Farm
from app.modules.registry.models import Valve
from tests.test_blocks_geo import rectangle
from tests.vectors import D, assert_matches, load

_VECTOR = next(c for c in load("records") if c["id"] == "records.product_concentration")


def _owner(
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
    email: str,
) -> tuple[Farm, dict[str, str], AppUser]:
    user = make_user(email, "ops-password")
    farm = make_farm(user, "Farm", Decimal("36"), Decimal("3"))
    return farm, auth_header(user), user


def _crop_id(client: TestClient, headers: dict[str, str], code: str = "table_grape") -> str:
    load_catalog()
    crops = client.get("/v1/catalog/crops", headers=headers)
    assert crops.status_code == 200
    return next(row["id"] for row in crops.json() if row["code"] == code)


def _put(
    client: TestClient,
    path: str,
    headers: dict[str, str],
    version: int,
    body: dict[str, object],
):
    return client.put(path, headers={**headers, "If-Match": str(version)}, json=body)


def _ops_block(
    client: TestClient,
    farm: Farm,
    headers: dict[str, str],
    *,
    name: str = "North",
) -> dict[str, object]:
    created = client.post(
        f"/v1/farms/{farm.id}/blocks",
        headers=headers,
        json={
            "name": name,
            "outline": rectangle(36.0, 3.0, 150, 150),
            "net_area_ha": "1.50",
            "crop_id": _crop_id(client, headers),
            "rows_total": 25,
        },
    )
    assert created.status_code == 201, created.text
    block_id = created.json()["id"]
    version = int(created.json()["version"])
    planted = _put(
        client,
        f"/v1/blocks/{block_id}/plantings",
        headers,
        version,
        {
            "plantings": [
                {
                    "density_input": "spacing",
                    "row_spacing_m": "4.00",
                    "tree_spacing_m": "2.00",
                }
            ]
        },
    )
    assert planted.status_code == 200, planted.text
    laid = _put(
        client,
        f"/v1/blocks/{block_id}/irrigation-layout",
        headers,
        int(planted.json()["version"]),
        {
            "system": "drip",
            "entry_mode": "typed_flow",
            "typed_flow_basis": "block",
            "typed_flow_m3h": "30",
        },
    )
    assert laid.status_code == 200, laid.text
    split = _put(
        client,
        f"/v1/blocks/{block_id}/valves",
        headers,
        int(laid.json()["version"]),
        {
            "valves": [
                {"name": "A", "row_from": 1, "row_to": 12},
                {"name": "B", "row_from": 13, "row_to": 25},
            ]
        },
    )
    assert split.status_code == 200, split.text
    done = client.post(
        f"/v1/blocks/{block_id}/complete",
        headers={**headers, "If-Match": str(split.json()["version"])},
    )
    assert done.status_code == 200, done.text
    body = done.json()
    assert isinstance(body, dict)
    return body


def _valve_ids(db: Session, block_id: str) -> tuple[str, str]:
    rows = list(
        db.scalars(
            select(Valve).where(Valve.block_id == block_id).order_by(Valve.sort, Valve.name)
        ).all()
    )
    assert len(rows) == 2
    return str(rows[0].id), str(rows[1].id)


def _create_product(
    client: TestClient,
    farm: Farm,
    headers: dict[str, str],
    *,
    name: str = "Fungicide X",
    phi: int | None = 21,
    reentry_h: int | None = 48,
) -> dict[str, object]:
    created = client.post(
        f"/v1/farms/{farm.id}/products",
        headers=headers,
        json={
            "name": name,
            "kind": "crop_protection",
            "unit": "ml",
            "preharvest_interval_days": phi,
            "reentry_h": reentry_h,
        },
    )
    assert created.status_code == 201, created.text
    return created.json()


def test_vector_through_api_and_valve_subset(
    client: TestClient,
    db: Session,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm, headers, _user = _owner(make_user, make_farm, auth_header, "ops-vector@agrect.app")
    block = _ops_block(client, farm, headers)
    block_id = str(block["id"])
    valve_a, _valve_b = _valve_ids(db, block_id)
    product = _create_product(client, farm, headers, name="Conc")

    preview = client.post(
        "/v1/calc/operation-product",
        headers=headers,
        json={
            "rate": _VECTOR["input"]["rate_ml_per_100l"],
            "rate_basis": "per_100l",
            "area_ha": _VECTOR["input"]["area_ha"],
            "water_l_ha": _VECTOR["input"]["water_l_ha"],
            "rate_unit": "ml",
        },
    )
    assert preview.status_code == 200, preview.text
    total_ml = D(str(preview.json()["total_qty"]))
    assert_matches(total_ml / D("1000"), _VECTOR["expected"]["total_l"])
    assert preview.json()["source"] == "calculated"
    assert preview.json()["total_unit"] == "ml"

    # Whole-block spray on 2.00 ha would need a 2 ha block; use valve A (0.72)
    # for subset area and a separate whole-block op on the block's 1.50 ha.
    op_valve = client.post(
        f"/v1/farms/{farm.id}/operations",
        headers=headers,
        json={
            "block_id": block_id,
            "valve_ids": [valve_a],
            "type": "crop_protection_spray",
            "date": "2026-08-01",
            "products": [
                {
                    "product_id": product["id"],
                    "rate": "100",
                    "rate_unit": "ml",
                    "rate_basis": "per_ha",
                }
            ],
        },
    )
    assert op_valve.status_code == 201, op_valve.text
    assert D(str(op_valve.json()["area_ha"])) == D("0.72")
    assert D(str(op_valve.json()["products"][0]["total_qty"])) == D("72")
    assert op_valve.json()["source"] == "calculated"

    # Concentration vector area via calc already checked; store whole-block line.
    op_block = client.post(
        f"/v1/farms/{farm.id}/operations",
        headers=headers,
        json={
            "block_id": block_id,
            "valve_ids": [],
            "type": "crop_protection_spray",
            "date": "2026-08-02",
            "products": [
                {
                    "product_id": product["id"],
                    "rate": _VECTOR["input"]["rate_ml_per_100l"],
                    "rate_unit": "ml",
                    "rate_basis": "per_100l",
                    "water_l_ha": _VECTOR["input"]["water_l_ha"],
                }
            ],
        },
    )
    assert op_block.status_code == 201, op_block.text
    assert D(str(op_block.json()["area_ha"])) == D("1.50")
    # 150 × 1000 × 1.50 / 100 = 2250 mL
    assert D(str(op_block.json()["products"][0]["total_qty"])) == D("2250")
    assert op_block.json()["products"][0]["total_unit"] == "ml"
    assert op_block.json()["safety"]["preharvest_interval_days"] == 21


def test_phi_warning_on_harvest(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm, headers, _user = _owner(make_user, make_farm, auth_header, "ops-phi@agrect.app")
    block = _ops_block(client, farm, headers, name="PHI")
    block_id = str(block["id"])
    product = _create_product(client, farm, headers, name="PHI Spray", phi=21)

    sprayed = client.post(
        f"/v1/farms/{farm.id}/operations",
        headers=headers,
        json={
            "block_id": block_id,
            "type": "crop_protection_spray",
            "date": "2026-08-31",
            "products": [
                {
                    "product_id": product["id"],
                    "rate": "1",
                    "rate_unit": "l",
                    "rate_basis": "per_ha",
                }
            ],
        },
    )
    assert sprayed.status_code == 201, sprayed.text

    early = client.post(
        f"/v1/blocks/{block_id}/harvest",
        headers=headers,
        json={
            "date": "2026-09-10",
            "quantity": "100",
            "unit": "kg",
            "basis": "block",
        },
    )
    assert early.status_code == 201, early.text
    warning = early.json()["preharvest_warning"]
    assert warning is not None
    assert warning["product"] == "PHI Spray"
    assert warning["spray_date"] == "2026-08-31"
    assert warning["days_since"] == 10
    assert warning["days_needed"] == 21

    listed = client.get(f"/v1/blocks/{block_id}/harvest", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["entries"][0]["preharvest_warning"]["days_since"] == 10

    ok = client.post(
        f"/v1/blocks/{block_id}/harvest",
        headers=headers,
        json={
            "date": "2026-09-21",
            "pass_no": 2,
            "quantity": "100",
            "unit": "kg",
            "basis": "block",
        },
    )
    assert ok.status_code == 201, ok.text
    assert ok.json()["preharvest_warning"] is None


def test_reentry_active_and_expired(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm, headers, _user = _owner(make_user, make_farm, auth_header, "ops-reentry@agrect.app")
    block = _ops_block(client, farm, headers, name="Reentry")
    block_id = str(block["id"])
    product = _create_product(client, farm, headers, name="Reentry Spray", reentry_h=2)

    start = datetime.now(UTC) - timedelta(minutes=30)
    active = client.post(
        f"/v1/farms/{farm.id}/operations",
        headers=headers,
        json={
            "block_id": block_id,
            "type": "herbicide",
            "date": start.date().isoformat(),
            "start_at": start.isoformat(),
            "duration_min": 30,
            "products": [
                {
                    "product_id": product["id"],
                    "rate": "1",
                    "rate_unit": "l",
                    "rate_basis": "per_block",
                }
            ],
        },
    )
    assert active.status_code == 201, active.text
    assert active.json()["safety"]["reentry_h"] == 2

    current = client.get(f"/v1/blocks/{block_id}/reentry", headers=headers)
    assert current.status_code == 200, current.text
    body = current.json()
    assert body is not None
    assert body["product"] == "Reentry Spray"
    assert body["until"] is not None

    # Expire by patching start far in the past.
    expired_start = datetime.now(UTC) - timedelta(hours=10)
    patched = client.patch(
        f"/v1/operations/{active.json()['id']}",
        headers={**headers, "If-Match": str(active.json()["version"])},
        json={"start_at": expired_start.isoformat()},
    )
    assert patched.status_code == 200, patched.text
    gone = client.get(f"/v1/blocks/{block_id}/reentry", headers=headers)
    assert gone.status_code == 200
    assert gone.json() is None


def test_product_in_use_cannot_delete(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm, headers, _user = _owner(make_user, make_farm, auth_header, "ops-inuse@agrect.app")
    block = _ops_block(client, farm, headers, name="InUse")
    product = _create_product(client, farm, headers, name="Locked")
    unused = _create_product(client, farm, headers, name="Free")

    op = client.post(
        f"/v1/farms/{farm.id}/operations",
        headers=headers,
        json={
            "block_id": block["id"],
            "type": "foliar_application",
            "date": "2026-07-01",
            "products": [
                {
                    "product_id": product["id"],
                    "rate": "2",
                    "rate_unit": "l",
                    "rate_basis": "per_ha",
                }
            ],
        },
    )
    assert op.status_code == 201, op.text

    blocked = client.delete(
        f"/v1/products/{product['id']}",
        headers={**headers, "If-Match": str(product["version"])},
    )
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "operations.product_in_use"

    ok = client.delete(
        f"/v1/products/{unused['id']}",
        headers={**headers, "If-Match": str(unused["version"])},
    )
    assert ok.status_code == 204


def test_operations_scoping_404(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm_a, headers_a, _user_a = _owner(make_user, make_farm, auth_header, "ops-a@agrect.app")
    _farm_b, headers_b, _user_b = _owner(make_user, make_farm, auth_header, "ops-b@agrect.app")
    block = _ops_block(client, farm_a, headers_a, name="Scoped")
    product = _create_product(client, farm_a, headers_a, name="Scoped Prod")
    op = client.post(
        f"/v1/farms/{farm_a.id}/operations",
        headers=headers_a,
        json={
            "block_id": block["id"],
            "type": "other",
            "date": "2026-06-01",
            "products": [
                {
                    "product_id": product["id"],
                    "rate": "1",
                    "rate_unit": "unit",
                    "rate_basis": "per_block",
                }
            ],
        },
    )
    assert op.status_code == 201, op.text

    assert client.get(f"/v1/farms/{farm_a.id}/products", headers=headers_b).status_code == 404
    assert client.get(f"/v1/operations/{op.json()['id']}", headers=headers_b).status_code == 404
    assert (
        client.patch(
            f"/v1/products/{product['id']}",
            headers={**headers_b, "If-Match": "1"},
            json={"name": "Hijack"},
        ).status_code
        == 404
    )
    assert client.get(f"/v1/blocks/{block['id']}/reentry", headers=headers_b).status_code == 404


def test_journal_lists_newest_first_and_filters(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm, headers, _user = _owner(make_user, make_farm, auth_header, "ops-journal@agrect.app")
    block = _ops_block(client, farm, headers, name="Journal")
    block_id = str(block["id"])
    product = _create_product(client, farm, headers, name="Journal Spray")

    op = client.post(
        f"/v1/farms/{farm.id}/operations",
        headers=headers,
        json={
            "block_id": block_id,
            "type": "crop_protection_spray",
            "date": "2026-08-01",
            "target": "Powdery mildew",
            "products": [
                {
                    "product_id": product["id"],
                    "rate": "150",
                    "rate_unit": "ml",
                    "rate_basis": "per_100l",
                    "water_l_ha": "1000",
                }
            ],
        },
    )
    assert op.status_code == 201, op.text
    assert op.json()["target"] == "Powdery mildew"

    harvest = client.post(
        f"/v1/blocks/{block_id}/harvest",
        headers=headers,
        json={
            "date": "2026-08-10",
            "quantity": "100",
            "unit": "kg",
            "basis": "block",
        },
    )
    assert harvest.status_code == 201, harvest.text

    load_catalog()
    stages = client.get(
        f"/v1/catalog/crops/{block['crop']['id']}/stages",
        headers=headers,
    )
    assert stages.status_code == 200, stages.text
    stage_id = stages.json()["stages"][0]["id"]
    season = client.put(
        f"/v1/blocks/{block_id}/seasons/2026",
        headers=headers,
        json={"start_date": "2026-03-01"},
    )
    assert season.status_code == 200, season.text
    observed = client.post(
        f"/v1/block-seasons/{season.json()['id']}/observations",
        headers=headers,
        json={"stage_def_id": stage_id, "observed_on": "2026-07-15"},
    )
    assert observed.status_code == 201, observed.text

    listed = client.get(f"/v1/blocks/{block_id}/journal", headers=headers)
    assert listed.status_code == 200, listed.text
    items = listed.json()["items"]
    kinds = [item["kind"] for item in items]
    assert kinds == ["harvest", "operation", "stage"]
    assert items[0]["link_id"] == harvest.json()["id"]
    assert items[1]["link_id"] == op.json()["id"]
    assert "Treatment" in items[1]["title"]
    assert "Powdery mildew" in (items[1]["details"] or "")
    assert items[1]["operation_type"] == "crop_protection_spray"
    assert items[2]["kind"] == "stage"
    assert items[2]["link_id"] == stage_id

    only_ops = client.get(
        f"/v1/blocks/{block_id}/journal",
        headers=headers,
        params={"types": "crop_protection_spray"},
    )
    assert only_ops.status_code == 200
    assert [item["kind"] for item in only_ops.json()["items"]] == ["operation"]

    only_harvest = client.get(
        f"/v1/blocks/{block_id}/journal",
        headers=headers,
        params={"types": "harvest", "from": "2026-08-01", "to": "2026-08-31"},
    )
    assert only_harvest.status_code == 200
    assert [item["kind"] for item in only_harvest.json()["items"]] == ["harvest"]

    empty = client.get(
        f"/v1/blocks/{block_id}/journal",
        headers=headers,
        params={"from": "2025-01-01", "to": "2025-12-31"},
    )
    assert empty.status_code == 200
    assert empty.json()["items"] == []


def test_stage_at_observed_predicted_or_null(
    client: TestClient,
    db: Session,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    from app.modules.phenology.models import (
        BlockSeason,
        PredictionLabel,
        StagePrediction,
    )

    farm, headers, _user = _owner(make_user, make_farm, auth_header, "ops-stageat@agrect.app")
    block = _ops_block(client, farm, headers, name="StageAt")
    block_id = str(block["id"])
    load_catalog()
    stages = client.get(
        f"/v1/catalog/crops/{block['crop']['id']}/stages",
        headers=headers,
    )
    assert stages.status_code == 200
    stage_a = stages.json()["stages"][0]
    stage_b = stages.json()["stages"][1]

    none_yet = client.get(
        f"/v1/blocks/{block_id}/stage-at",
        headers=headers,
        params={"date": "2026-05-01"},
    )
    assert none_yet.status_code == 200
    assert none_yet.json() == {"stage": None, "date": None, "label": None}

    season = client.put(
        f"/v1/blocks/{block_id}/seasons/2026",
        headers=headers,
        json={"start_date": "2026-03-01"},
    )
    assert season.status_code == 200
    season_id = season.json()["id"]

    observed = client.post(
        f"/v1/block-seasons/{season_id}/observations",
        headers=headers,
        json={"stage_def_id": stage_a["id"], "observed_on": "2026-04-10"},
    )
    assert observed.status_code == 201, observed.text

    at_obs = client.get(
        f"/v1/blocks/{block_id}/stage-at",
        headers=headers,
        params={"date": "2026-04-20"},
    )
    assert at_obs.status_code == 200
    body = at_obs.json()
    assert body["label"] == "observed"
    assert body["date"] == "2026-04-10"
    assert body["stage"]["id"] == stage_a["id"]
    assert body["stage"]["code"] == stage_a["code"]

    # Predicted-only path: clear observations by deleting, then insert a prediction.
    deleted = client.delete(
        f"/v1/block-seasons/{season_id}/observations/{observed.json()['id']}",
        headers=headers,
    )
    assert deleted.status_code == 204
    season_row = db.get(BlockSeason, season_id)
    assert season_row is not None
    # Recomputing after the delete already left a stage_b prediction row
    # (predicted_on=None, which stage-at ignores); upsert it to a dated,
    # predicted row instead of inserting a duplicate primary key.
    pred_row = db.scalar(
        select(StagePrediction).where(
            StagePrediction.block_season_id == season_row.id,
            StagePrediction.stage_def_id == stage_b["id"],
        )
    )
    if pred_row is None:
        pred_row = StagePrediction(
            block_season_id=season_row.id,
            stage_def_id=stage_b["id"],
            farm_id=farm.id,
            earliest=None,
            latest=None,
            dd_needed=None,
            dd_counted=None,
            reason=None,
            inputs_hash="a" * 64,
        )
        db.add(pred_row)
    pred_row.label = PredictionLabel.predicted
    pred_row.predicted_on = date(2026, 5, 1)
    pred_row.run_at = datetime.now(UTC)
    db.commit()

    at_pred = client.get(
        f"/v1/blocks/{block_id}/stage-at",
        headers=headers,
        params={"date": "2026-05-15"},
    )
    assert at_pred.status_code == 200
    pred = at_pred.json()
    assert pred["label"] == "predicted"
    assert pred["date"] == "2026-05-01"
    assert pred["stage"]["id"] == stage_b["id"]

    before = client.get(
        f"/v1/blocks/{block_id}/stage-at",
        headers=headers,
        params={"date": "2026-04-01"},
    )
    assert before.status_code == 200
    assert before.json()["label"] is None
