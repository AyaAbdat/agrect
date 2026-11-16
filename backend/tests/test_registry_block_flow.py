import uuid
from collections.abc import Callable
from decimal import Decimal

from fastapi.testclient import TestClient

from app.modules.auth.models import AppUser
from app.modules.catalog.loader import load_catalog
from app.modules.farms.models import Farm
from tests.test_blocks_geo import rectangle
from tests.vectors import assert_matches, load

_DRIP = next(case for case in load("registry") if case["id"] == "registry.drip_flow")


def _owner(
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
    email: str = "registry-flow@agrect.app",
) -> tuple[Farm, dict[str, str]]:
    user = make_user(email, "registry-password")
    farm = make_farm(user, "Farm", Decimal("36"), Decimal("3"))
    return farm, auth_header(user)


def _crop_id(client: TestClient, headers: dict[str, str]) -> str:
    load_catalog()
    crops = client.get("/v1/catalog/crops", headers=headers).json()
    return next(row["id"] for row in crops if row["code"] == "olive")


def _draft(
    client: TestClient,
    farm: Farm,
    headers: dict[str, str],
    *,
    name: str = "North",
    with_square: bool = False,
    crop: bool = False,
    rows_total: int | None = None,
) -> dict[str, object]:
    body: dict[str, object] = {"name": name}
    if with_square:
        body["outline"] = rectangle(36.0, 3.0, 102, 102)
        body["net_area_ha"] = "1"
    if crop:
        body["crop_id"] = _crop_id(client, headers)
    if rows_total is not None:
        body["rows_total"] = rows_total
    response = client.post(f"/v1/farms/{farm.id}/blocks", headers=headers, json=body)
    assert response.status_code == 201
    return response.json()


def _put(
    client: TestClient,
    path: str,
    headers: dict[str, str],
    version: int,
    body: dict[str, object],
) -> object:
    return client.put(
        path,
        headers={**headers, "If-Match": str(version)},
        json=body,
    )


def test_square_drip_flow_completes(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm, headers = _owner(make_user, make_farm, auth_header)
    created = _draft(
        client,
        farm,
        headers,
        with_square=True,
        crop=True,
        rows_total=25,
    )
    block_id = str(created["id"])
    missing = client.put(
        f"/v1/blocks/{block_id}/plantings",
        headers=headers,
        json={
            "plantings": [
                {
                    "density_input": "spacing",
                    "row_spacing_m": "4.00",
                    "tree_spacing_m": "1.50",
                }
            ]
        },
    )
    assert missing.status_code == 428
    assert missing.json() == {"code": "conflict.version_required"}
    planted = _put(
        client,
        f"/v1/blocks/{block_id}/plantings",
        headers,
        int(created["version"]),
        {
            "plantings": [
                {
                    "density_input": "spacing",
                    "row_spacing_m": "4.00",
                    "tree_spacing_m": "1.50",
                }
            ]
        },
    )
    assert planted.status_code == 200
    laid = _put(
        client,
        f"/v1/blocks/{block_id}/irrigation-layout",
        headers,
        planted.json()["version"],
        {
            "system": "drip",
            "entry_mode": "layout",
            "laterals_per_row": 2,
            "emitter_spacing_m": "0.75",
            "emitter_flow_lph": "4.0",
        },
    )
    assert laid.status_code == 200
    body = laid.json()
    layout = body["irrigation_layout"]
    assert_matches(Decimal(layout["q_ha_m3h"]), _DRIP["expected"]["q_ha_m3h"])
    assert_matches(Decimal(layout["rate_mm_h"]), _DRIP["expected"]["rate_mm_h"])
    assert layout["sources"]["emitter_flow_lph"] == "entered"
    assert layout["sources"]["q_ha_m3h"] == "calculated"
    assert layout["sources"]["q_block_m3h"] == "calculated"
    assert layout["sources"]["rate_mm_h"] == "calculated"
    planting = body["plantings"][0]
    assert planting["sources"]["row_spacing_m"] == "entered"
    assert planting["sources"]["tree_spacing_m"] == "entered"
    assert planting["sources"]["trees_per_ha"] == "calculated"
    assert planting["sources"]["trees_count"] == "calculated"
    assert planting["sources"]["area_ha"] == "calculated"
    assert planting["trees_per_ha"] == 1666
    assert body["trees_count"] == 1666
    assert body["valves"][0]["name"] == "V1"
    assert body["valves"][0]["row_from"] == 1
    assert body["valves"][0]["row_to"] == 25
    assert body["valves"][0]["sources"]["name"] == "entered"
    assert body["valves"][0]["sources"]["q_m3h"] == "calculated"
    assert body["valves"][0]["sources"]["area_ha"] == "calculated"
    listed = client.get(f"/v1/farms/{farm.id}/blocks", headers=headers)
    assert listed.status_code == 200
    row = listed.json()[0]
    assert row["trees_count"] == 1666
    assert row["q_block_m3h"] == body["q_block_m3h"]
    assert row["rate_mm_h"] == body["rate_mm_h"]
    done = client.post(
        f"/v1/blocks/{block_id}/complete",
        headers={**headers, "If-Match": str(body["version"])},
    )
    assert done.status_code == 200
    assert done.json()["status"] == "complete"
    assert done.headers["etag"] == str(done.json()["version"])
    history = client.get(f"/v1/blocks/{block_id}/history", headers=headers)
    assert history.json()[0]["reason"] == "completed"
    assert history.json()[0]["changed_fields"] == ["status"]
    assert history.json()[0]["entity_type"] == "block"


def test_two_valves_sum_to_the_block(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm, headers = _owner(make_user, make_farm, auth_header, "valves@agrect.app")
    created = _draft(client, farm, headers, with_square=True, crop=True, rows_total=25)
    block_id = str(created["id"])
    planted = _put(
        client,
        f"/v1/blocks/{block_id}/plantings",
        headers,
        int(created["version"]),
        {
            "plantings": [
                {
                    "density_input": "spacing",
                    "row_spacing_m": "4.00",
                    "tree_spacing_m": "1.50",
                }
            ]
        },
    )
    laid = _put(
        client,
        f"/v1/blocks/{block_id}/irrigation-layout",
        headers,
        planted.json()["version"],
        {
            "system": "drip",
            "entry_mode": "layout",
            "laterals_per_row": 2,
            "emitter_spacing_m": "0.75",
            "emitter_flow_lph": "4.0",
        },
    )
    split = _put(
        client,
        f"/v1/blocks/{block_id}/valves",
        headers,
        laid.json()["version"],
        {
            "valves": [
                {"name": "V1", "row_from": 1, "row_to": 10},
                {"name": "V2", "row_from": 11, "row_to": 25},
            ]
        },
    )
    assert split.status_code == 200
    body = split.json()
    areas = sum(Decimal(valve["area_ha"]) for valve in body["valves"])
    flows = sum(Decimal(valve["q_m3h"]) for valve in body["valves"])
    assert areas == Decimal(body["net_area_ha"])
    assert flows == Decimal(body["q_block_m3h"])


def test_valve_rows_must_fit_and_not_overlap(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm, headers = _owner(make_user, make_farm, auth_header, "rows@agrect.app")
    created = _draft(client, farm, headers, rows_total=25)
    block_id = str(created["id"])
    overlap = _put(
        client,
        f"/v1/blocks/{block_id}/valves",
        headers,
        int(created["version"]),
        {
            "valves": [
                {"name": "V1", "row_from": 1, "row_to": 10},
                {"name": "V2", "row_from": 10, "row_to": 25},
            ]
        },
    )
    assert overlap.status_code == 422
    assert overlap.json() == {
        "code": "validation_error",
        "fields": {"valves.1.row_from": "registry.valve_rows_overlap"},
    }
    invalid = _put(
        client,
        f"/v1/blocks/{block_id}/valves",
        headers,
        int(created["version"]),
        {"valves": [{"name": "V1", "row_from": 1, "row_to": 26}]},
    )
    assert invalid.status_code == 422
    assert invalid.json() == {
        "code": "validation_error",
        "fields": {"valves.0.row_from": "registry.valve_rows_invalid"},
    }


def test_name_only_draft_is_incomplete(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm, headers = _owner(make_user, make_farm, auth_header, "draft@agrect.app")
    created = _draft(client, farm, headers)
    response = client.post(
        f"/v1/blocks/{created['id']}/complete",
        headers={**headers, "If-Match": str(created["version"])},
    )
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "block.incomplete"
    assert set(body["fields"].values()) == {
        "block.outline_required",
        "block.net_area_required",
        "block.crop_required",
        "planting.spacing_required",
        "irrigation.layout_incomplete",
        "block.rows_required",
    }
    assert len(body["fields"]) == 6


def test_complete_block_requires_a_reason_to_change_spacing(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm, headers = _owner(make_user, make_farm, auth_header, "reason@agrect.app")
    created = _draft(client, farm, headers, with_square=True, crop=True, rows_total=25)
    block_id = str(created["id"])
    planted = _put(
        client,
        f"/v1/blocks/{block_id}/plantings",
        headers,
        int(created["version"]),
        {
            "plantings": [
                {
                    "density_input": "spacing",
                    "row_spacing_m": "4.00",
                    "tree_spacing_m": "1.50",
                }
            ]
        },
    )
    laid = _put(
        client,
        f"/v1/blocks/{block_id}/irrigation-layout",
        headers,
        planted.json()["version"],
        {
            "system": "drip",
            "entry_mode": "layout",
            "laterals_per_row": 2,
            "emitter_spacing_m": "0.75",
            "emitter_flow_lph": "4.0",
        },
    )
    done = client.post(
        f"/v1/blocks/{block_id}/complete",
        headers={**headers, "If-Match": str(laid.json()["version"])},
    )
    assert done.status_code == 200
    version = done.json()["version"]
    previous_q = done.json()["q_block_m3h"]
    refused = _put(
        client,
        f"/v1/blocks/{block_id}/plantings",
        headers,
        version,
        {
            "plantings": [
                {
                    "density_input": "spacing",
                    "row_spacing_m": "5.00",
                    "tree_spacing_m": "1.50",
                }
            ]
        },
    )
    assert refused.status_code == 422
    assert refused.json() == {
        "code": "validation_error",
        "fields": {"reason": "record.reason_required"},
    }
    changed = _put(
        client,
        f"/v1/blocks/{block_id}/plantings",
        headers,
        version,
        {
            "plantings": [
                {
                    "density_input": "spacing",
                    "row_spacing_m": "5.00",
                    "tree_spacing_m": "1.50",
                }
            ],
            "reason": "wider rows",
        },
    )
    assert changed.status_code == 200
    assert changed.json()["q_block_m3h"] != previous_q
    history = client.get(f"/v1/blocks/{block_id}/history", headers=headers)
    fields = history.json()[0]["changed_fields"]
    assert "planting.row_spacing_m" in fields
    assert "irrigation_layout.q_ha_m3h" in fields
    assert "irrigation_layout.q_block_m3h" in fields
    assert history.json()[0]["reason"] == "wider rows"


def test_missing_emitter_flow_leaves_q_null(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm, headers = _owner(make_user, make_farm, auth_header, "partial@agrect.app")
    created = _draft(client, farm, headers, with_square=True, rows_total=25)
    block_id = str(created["id"])
    planted = _put(
        client,
        f"/v1/blocks/{block_id}/plantings",
        headers,
        int(created["version"]),
        {
            "plantings": [
                {
                    "density_input": "spacing",
                    "row_spacing_m": "4.00",
                    "tree_spacing_m": "1.50",
                }
            ]
        },
    )
    laid = _put(
        client,
        f"/v1/blocks/{block_id}/irrigation-layout",
        headers,
        planted.json()["version"],
        {
            "system": "drip",
            "entry_mode": "layout",
            "laterals_per_row": 2,
            "emitter_spacing_m": "0.75",
        },
    )
    assert laid.status_code == 200
    body = laid.json()
    assert body["irrigation_layout"]["q_ha_m3h"] is None
    assert body["irrigation_layout"]["q_block_m3h"] is None
    assert body["irrigation_layout"]["rate_mm_h"] is None
    assert body["q_block_m3h"] is None
    assert body["rate_mm_h"] is None
    assert body["valves"][0]["q_m3h"] is None


def test_other_user_cannot_put_plantings(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm, headers = _owner(make_user, make_farm, auth_header, "owner-a@agrect.app")
    created = _draft(client, farm, headers)
    _user_b = make_user("owner-b@agrect.app", "password-b")
    headers_b = auth_header(_user_b)
    response = client.put(
        f"/v1/blocks/{created['id']}/plantings",
        headers={**headers_b, "If-Match": "1"},
        json={"plantings": []},
    )
    assert response.status_code == 404
    assert response.json() == {"code": "block.not_found"}
    missing = client.put(
        f"/v1/blocks/{uuid.uuid4()}/irrigation-layout",
        headers={**headers, "If-Match": "1"},
        json={"system": "drip", "entry_mode": "layout"},
    )
    assert missing.status_code == 404
    assert missing.json() == {"code": "block.not_found"}


def test_typed_valve_basis_uses_valve_flows(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    user = make_user("preview-valve@agrect.app", "registry-password")
    response = client.post(
        "/v1/calc/registry/irrigation",
        headers=auth_header(user),
        json={
            "entry_mode": "typed_flow",
            "typed_flow_basis": "valve",
            "net_area_ha": "1",
            "rows_total": 25,
            "valves": [
                {"row_from": 1, "row_to": 10, "typed_q_m3h": "1.5"},
                {"row_from": 11, "row_to": 25, "typed_q_m3h": "2.5"},
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["q_ha_m3h"] == "4.00"
    assert body["q_block_m3h"] == "4.00"
    assert body["rate_mm_h"] == "0.40"
    assert body["source"] == "calculated"


def test_typed_block_flow_is_stored_per_hectare(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm, headers = _owner(make_user, make_farm, auth_header, "typed-ha@agrect.app")
    created = client.post(
        f"/v1/farms/{farm.id}/blocks",
        headers=headers,
        json={"name": "Typed", "net_area_ha": "1.50"},
    )
    assert created.status_code == 201
    block_id = created.json()["id"]
    laid = _put(
        client,
        f"/v1/blocks/{block_id}/irrigation-layout",
        headers,
        int(created.json()["version"]),
        {
            "system": "drip",
            "entry_mode": "typed_flow",
            "typed_flow_basis": "block",
            "typed_flow_m3h": "40",
        },
    )
    assert laid.status_code == 200
    layout = laid.json()["irrigation_layout"]
    assert layout["q_ha_m3h"] == "26.67"
    assert layout["q_block_m3h"] == "40.00"
    assert layout["sources"]["q_ha_m3h"] == "calculated"
