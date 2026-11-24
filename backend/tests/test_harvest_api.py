"""Harvest API: all bases match the crates vector; quality, summary, scoping."""

from collections.abc import Callable
from datetime import date
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

_VECTOR = next(c for c in load("records") if c["id"] == "records.harvest_crates")
_EXPECTED_KG = _VECTOR["expected"]["kg"]
_EXPECTED_KG_HA = _VECTOR["expected"]["kg_ha"]


def _owner(
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
    email: str,
) -> tuple[Farm, dict[str, str], AppUser]:
    user = make_user(email, "harvest-password")
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


def _harvest_block(
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
    assert rows[0].area_ha == D("0.72")
    assert rows[1].area_ha == D("0.78")
    return str(rows[0].id), str(rows[1].id)


def _assert_yield(body: dict[str, object], *, entry: bool = True) -> None:
    assert body["source"] == "calculated"
    if entry:
        assert body["preharvest_warning"] is None
    assert_matches(D(str(body["kg"])), _EXPECTED_KG)
    assert_matches(D(str(body["kg_ha"])), _EXPECTED_KG_HA)


def test_all_bases_match_vector(
    client: TestClient,
    db: Session,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm, headers, _user = _owner(make_user, make_farm, auth_header, "harvest-bases@agrect.app")
    block = _harvest_block(client, farm, headers)
    block_id = str(block["id"])
    valve_a, valve_b = _valve_ids(db, block_id)
    day = "2026-09-15"

    crates = client.post(
        f"/v1/blocks/{block_id}/harvest",
        headers=headers,
        json={
            "date": day,
            "quantity": "250",
            "unit": "crate",
            "unit_weight_kg": "18",
            "basis": "block",
        },
    )
    assert crates.status_code == 201, crates.text
    _assert_yield(crates.json())
    assert D(crates.json()["area_ha"]) == D("1.50")

    tonnes = client.post(
        f"/v1/blocks/{block_id}/harvest",
        headers=headers,
        json={
            "date": day,
            "pass_no": 2,
            "quantity": "4.5",
            "unit": "t",
            "basis": "block",
        },
    )
    assert tonnes.status_code == 201, tonnes.text
    _assert_yield(tonnes.json())

    valve1 = client.post(
        f"/v1/blocks/{block_id}/harvest",
        headers=headers,
        json={
            "date": day,
            "pass_no": 3,
            "quantity": "2160",
            "unit": "kg",
            "basis": "valve",
            "valve_id": valve_a,
        },
    )
    valve2 = client.post(
        f"/v1/blocks/{block_id}/harvest",
        headers=headers,
        json={
            "date": day,
            "pass_no": 3,
            "quantity": "2340",
            "unit": "kg",
            "basis": "valve",
            "valve_id": valve_b,
        },
    )
    assert valve1.status_code == 201, valve1.text
    assert valve2.status_code == 201, valve2.text
    assert_matches(D(valve1.json()["kg"]) + D(valve2.json()["kg"]), _EXPECTED_KG)
    assert_matches(D(valve1.json()["kg_ha"]), _EXPECTED_KG_HA)
    assert_matches(D(valve2.json()["kg_ha"]), _EXPECTED_KG_HA)
    assert valve1.json()["source"] == "calculated"
    assert valve2.json()["source"] == "calculated"

    rows = client.post(
        f"/v1/blocks/{block_id}/harvest",
        headers=headers,
        json={
            "date": day,
            "pass_no": 4,
            "quantity": "4500",
            "unit": "kg",
            "basis": "rows",
            "basis_count": "25",
        },
    )
    assert rows.status_code == 201, rows.text
    _assert_yield(rows.json())

    trees_count = 1250 * D("1.50")
    trees = client.post(
        f"/v1/blocks/{block_id}/harvest",
        headers=headers,
        json={
            "date": day,
            "pass_no": 5,
            "quantity": "4500",
            "unit": "kg",
            "basis": "trees",
            "basis_count": format(trees_count, "f"),
        },
    )
    assert trees.status_code == 201, trees.text
    _assert_yield(trees.json())

    preview = client.post(
        "/v1/calc/harvest",
        headers=headers,
        json={
            "block_id": block_id,
            "quantity": "250",
            "unit": "crate",
            "unit_weight_kg": "18",
            "basis": "block",
        },
    )
    assert preview.status_code == 200, preview.text
    _assert_yield(preview.json(), entry=False)


def test_quality_optional_and_patch_recomputes(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm, headers, _user = _owner(make_user, make_farm, auth_header, "harvest-quality@agrect.app")
    block = _harvest_block(client, farm, headers, name="Quality")
    block_id = str(block["id"])
    created = client.post(
        f"/v1/blocks/{block_id}/harvest",
        headers=headers,
        json={
            "date": "2026-09-20",
            "quantity": "250",
            "unit": "crate",
            "unit_weight_kg": "18",
            "basis": "block",
            "quality": {"brix": "18.5", "waste_pct": "2", "size_grade": {"A": 70, "B": 30}},
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["quality"]["brix"] == "18.5"
    assert body["quality"]["waste_pct"] == "2"
    assert body["quality"]["size_grade"] == {"A": 70, "B": 30}
    entry_id = body["id"]

    patched = client.patch(
        f"/v1/blocks/{block_id}/harvest/{entry_id}",
        headers={**headers, "If-Match": str(body["version"])},
        json={"quantity": "125", "unit_weight_kg": "18"},
    )
    assert patched.status_code == 200, patched.text
    assert_matches(D(patched.json()["kg"]), "2250")
    assert_matches(D(patched.json()["kg_ha"]), "1500")
    assert patched.json()["version"] == 2
    assert patched.json()["quality"]["brix"] == "18.5"


def test_size_grade_sum_invalid(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm, headers, _user = _owner(make_user, make_farm, auth_header, "harvest-grades@agrect.app")
    block = _harvest_block(client, farm, headers, name="Grades")
    refused = client.post(
        f"/v1/blocks/{block['id']}/harvest",
        headers=headers,
        json={
            "date": "2026-09-20",
            "quantity": "100",
            "unit": "kg",
            "basis": "block",
            "quality": {"size_grade": {"A": 60, "B": 50}},
        },
    )
    assert refused.status_code == 422, refused.text
    assert refused.json()["fields"]["size_grade"] == "harvest.size_grade_sum_invalid"

    over_one = client.post(
        f"/v1/blocks/{block['id']}/harvest",
        headers=headers,
        json={
            "date": "2026-09-20",
            "quantity": "100",
            "unit": "kg",
            "basis": "block",
            "quality": {"size_grade": {"A": 101}},
        },
    )
    assert over_one.status_code == 422, over_one.text
    assert over_one.json()["fields"]["size_grade"] == "harvest.size_grade_sum_invalid"


def test_summary_sums_passes(
    client: TestClient,
    db: Session,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm, headers, _user = _owner(make_user, make_farm, auth_header, "harvest-summary@agrect.app")
    block = _harvest_block(client, farm, headers, name="Summary")
    block_id = str(block["id"])
    for pass_no, qty in ((1, "2000"), (2, "2500")):
        saved = client.post(
            f"/v1/blocks/{block_id}/harvest",
            headers=headers,
            json={
                "date": "2026-08-01",
                "pass_no": pass_no,
                "quantity": qty,
                "unit": "kg",
                "basis": "block",
            },
        )
        assert saved.status_code == 201, saved.text

    summary = client.get(
        f"/v1/farms/{farm.id}/harvest/summary",
        headers=headers,
        params={"season": 2026},
    )
    assert summary.status_code == 200, summary.text
    body = summary.json()
    assert body["season"] == 2026
    assert_matches(D(body["farm"]["kg_total"]), "4500")
    assert_matches(D(body["farm"]["kg_ha"]), "3000")
    assert body["farm"]["blocks_harvested"] == 1
    block_row = next(row for row in body["blocks"] if row["block_id"] == block_id)
    assert block_row["passes"] == 2
    assert_matches(D(block_row["kg_total"]), "4500")
    assert_matches(D(block_row["kg_ha"]), "3000")

    empty_year = client.get(
        f"/v1/farms/{farm.id}/harvest/summary",
        headers=headers,
        params={"season": 2025},
    )
    assert empty_year.status_code == 200
    empty = empty_year.json()
    assert empty["farm"]["kg_total"] == "0"
    assert empty["farm"]["kg_ha"] is None
    assert empty["farm"]["blocks_harvested"] == 0
    assert empty["blocks"][0]["passes"] == 0

    valve_a, valve_b = _valve_ids(db, block_id)
    for valve_id, qty in ((valve_a, "1000"), (valve_b, "500")):
        same_pass = client.post(
            f"/v1/blocks/{block_id}/harvest",
            headers=headers,
            json={
                "date": "2026-08-15",
                "pass_no": 3,
                "quantity": qty,
                "unit": "kg",
                "basis": "valve",
                "valve_id": valve_id,
            },
        )
        assert same_pass.status_code == 201, same_pass.text

    after = client.get(
        f"/v1/farms/{farm.id}/harvest/summary",
        headers=headers,
        params={"season": 2026},
    )
    assert after.status_code == 200, after.text
    after_body = after.json()
    after_block = next(row for row in after_body["blocks"] if row["block_id"] == block_id)
    assert after_block["passes"] == 3
    assert after_body["farm"]["blocks_harvested"] == 1


def test_other_farm_and_foreign_valve(
    client: TestClient,
    db: Session,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm_a, headers_a, _ = _owner(make_user, make_farm, auth_header, "harvest-a@agrect.app")
    farm_b, headers_b, _ = _owner(make_user, make_farm, auth_header, "harvest-b@agrect.app")
    block_a = _harvest_block(client, farm_a, headers_a, name="A")
    block_b = _harvest_block(client, farm_b, headers_b, name="B")
    block_a_id = str(block_a["id"])
    block_b_id = str(block_b["id"])
    _valve_a, _ = _valve_ids(db, block_a_id)
    valve_b, _ = _valve_ids(db, block_b_id)

    denied = client.get(f"/v1/blocks/{block_a_id}/harvest", headers=headers_b)
    assert denied.status_code == 404

    denied_post = client.post(
        f"/v1/blocks/{block_a_id}/harvest",
        headers=headers_b,
        json={
            "date": "2026-09-01",
            "quantity": "10",
            "unit": "kg",
            "basis": "block",
        },
    )
    assert denied_post.status_code == 404

    denied_summary = client.get(
        f"/v1/farms/{farm_a.id}/harvest/summary",
        headers=headers_b,
        params={"season": 2026},
    )
    assert denied_summary.status_code == 404

    foreign_valve = client.post(
        f"/v1/blocks/{block_a_id}/harvest",
        headers=headers_a,
        json={
            "date": "2026-09-01",
            "quantity": "10",
            "unit": "kg",
            "basis": "valve",
            "valve_id": valve_b,
        },
    )
    assert foreign_valve.status_code == 422
    assert foreign_valve.json()["fields"]["valve_id"] == "harvest.valve_not_in_block"

    # Ensure block_b exists for the foreign valve lookup above.
    assert block_b_id


def test_harvest_fields_per_crop(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    _farm, headers, _ = _owner(make_user, make_farm, auth_header, "harvest-fields@agrect.app")
    grape = _crop_id(client, headers, "table_grape")
    olive = _crop_id(client, headers, "olive")
    wheat = _crop_id(client, headers, "wheat")

    grape_fields = client.get(f"/v1/catalog/crops/{grape}/harvest-fields", headers=headers)
    assert grape_fields.status_code == 200
    assert grape_fields.json()["fields"] == ["brix", "size_grade", "waste_pct"]

    olive_fields = client.get(f"/v1/catalog/crops/{olive}/harvest-fields", headers=headers)
    assert olive_fields.status_code == 200
    assert olive_fields.json()["fields"] == ["waste_pct", "moisture_pct"]

    wheat_fields = client.get(f"/v1/catalog/crops/{wheat}/harvest-fields", headers=headers)
    assert wheat_fields.status_code == 200
    assert wheat_fields.json()["fields"] == [
        "moisture_pct",
        "protein_pct",
        "test_weight_kg_hl",
    ]


def test_missing_unit_weight_rejected(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm, headers, _ = _owner(make_user, make_farm, auth_header, "harvest-weight@agrect.app")
    block = _harvest_block(client, farm, headers, name="Weight")
    refused = client.post(
        f"/v1/blocks/{block['id']}/harvest",
        headers=headers,
        json={
            "date": str(date(2026, 9, 1)),
            "quantity": "10",
            "unit": "crate",
            "basis": "block",
        },
    )
    assert refused.status_code == 422
    assert refused.json()["fields"]["unit_weight_kg"] == "harvest.unit_weight_required"
