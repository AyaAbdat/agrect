"""Inputs and cost API: prices, stock moves, automatic posting, cost rollups."""

from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.auth.models import AppUser
from app.modules.farms.models import Farm
from tests.test_operations_api import _ops_block, _owner, _valve_ids
from tests.vectors import D


def _product(
    client: TestClient,
    farm: Farm,
    headers: dict[str, str],
    *,
    name: str = "Test fungicide",
    unit: str = "l",
    phi: int | None = 21,
    reentry_h: int | None = 24,
) -> dict[str, object]:
    created = client.post(
        f"/v1/farms/{farm.id}/products",
        headers=headers,
        json={
            "name": name,
            "kind": "crop_protection",
            "unit": unit,
            "preharvest_interval_days": phi,
            "reentry_h": reentry_h,
        },
    )
    assert created.status_code == 201, created.text
    return created.json()


def _price(
    client: TestClient,
    farm: Farm,
    headers: dict[str, str],
    body: dict[str, object],
) -> dict[str, object]:
    created = client.post(f"/v1/farms/{farm.id}/prices", headers=headers, json=body)
    assert created.status_code == 201, created.text
    return created.json()


def _treatment(
    client: TestClient,
    farm: Farm,
    headers: dict[str, str],
    block_id: str,
    product_id: str,
    rate: str,
    date: str = "2026-08-01",
) -> dict[str, object]:
    created = client.post(
        f"/v1/farms/{farm.id}/operations",
        headers=headers,
        json={
            "block_id": block_id,
            "type": "crop_protection_spray",
            "date": date,
            "products": [
                {
                    "product_id": product_id,
                    "rate": rate,
                    "rate_unit": "l",
                    "rate_basis": "per_block",
                }
            ],
        },
    )
    assert created.status_code == 201, created.text
    return created.json()


def _stock_item(client: TestClient, farm: Farm, headers: dict[str, str], product_id: str):
    stock = client.get(f"/v1/farms/{farm.id}/stock", headers=headers)
    assert stock.status_code == 200, stock.text
    return next((item for item in stock.json()["items"] if item["product_id"] == product_id), None)


def test_operation_posts_stock_and_cost(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm, headers, _user = _owner(make_user, make_farm, auth_header, "cost-core@agrect.app")
    block = _ops_block(client, farm, headers)
    block_id = str(block["id"])
    product = _product(client, farm, headers)
    _price(
        client,
        farm,
        headers,
        {
            "resource": "product",
            "product_id": product["id"],
            "valid_from": "2026-01-01",
            "dzd_per_unit": "1200",
        },
    )

    op = _treatment(client, farm, headers, block_id, str(product["id"]), "2.25")

    item = _stock_item(client, farm, headers, str(product["id"]))
    assert item is not None
    assert D(str(item["on_hand"])) == D("-2.25")
    assert item["unit"] == "l"
    assert D(str(item["uses_this_season"])) == D("2.25")

    costs = client.get(f"/v1/blocks/{block_id}/costs", headers=headers, params={"season": 2026})
    assert costs.status_code == 200, costs.text
    body = costs.json()
    assert D(str(body["total_dzd"])) == D("2700")
    assert D(str(body["by_source"]["product"])) == D("2700")
    assert D(str(body["per_ha_dzd"])) == D("1800")
    assert len(body["by_operation"]) == 1
    assert body["by_operation"][0]["date"] == "2026-08-01"
    assert body["by_operation"][0]["type"] == "crop_protection_spray"
    assert D(str(body["by_operation"][0]["dzd"])) == D("2700")
    assert body["missing_prices"] == []

    farm_costs = client.get(f"/v1/farms/{farm.id}/costs", headers=headers, params={"season": 2026})
    assert farm_costs.status_code == 200, farm_costs.text
    fc = farm_costs.json()
    assert D(str(fc["total_dzd"])) == D("2700")
    assert D(str(fc["per_ha_dzd"])) == D("1800")
    assert any(D(str(b["total_dzd"])) == D("2700") for b in fc["blocks"])

    # Edit the dose -> move and line are replaced.
    edited = client.patch(
        f"/v1/operations/{op['id']}",
        headers={**headers, "If-Match": str(op["version"])},
        json={
            "products": [
                {
                    "product_id": product["id"],
                    "rate": "1",
                    "rate_unit": "l",
                    "rate_basis": "per_block",
                }
            ]
        },
    )
    assert edited.status_code == 200, edited.text
    item = _stock_item(client, farm, headers, str(product["id"]))
    assert D(str(item["on_hand"])) == D("-1")
    costs = client.get(f"/v1/blocks/{block_id}/costs", headers=headers, params={"season": 2026})
    assert D(str(costs.json()["total_dzd"])) == D("1200")

    # Delete the operation -> move and line are removed.
    removed = client.delete(
        f"/v1/operations/{op['id']}",
        headers={**headers, "If-Match": str(edited.json()["version"])},
    )
    assert removed.status_code == 204
    item = _stock_item(client, farm, headers, str(product["id"]))
    assert D(str(item["on_hand"])) == D("0")
    costs = client.get(f"/v1/blocks/{block_id}/costs", headers=headers, params={"season": 2026})
    assert D(str(costs.json()["total_dzd"])) == D("0")
    assert costs.json()["by_operation"] == []


def test_missing_price_then_added_recomputes(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm, headers, _user = _owner(make_user, make_farm, auth_header, "cost-late@agrect.app")
    block = _ops_block(client, farm, headers, name="Late")
    block_id = str(block["id"])
    product = _product(client, farm, headers, name="Late fungicide")
    _treatment(client, farm, headers, block_id, str(product["id"]), "2.25")

    # No price yet: no cost, product listed under missing_prices.
    costs = client.get(f"/v1/blocks/{block_id}/costs", headers=headers, params={"season": 2026})
    assert D(str(costs.json()["total_dzd"])) == D("0")
    assert costs.json()["missing_prices"] == ["Late fungicide"]
    # The stock use is still posted regardless of price.
    item = _stock_item(client, farm, headers, str(product["id"]))
    assert D(str(item["on_hand"])) == D("-2.25")

    _price(
        client,
        farm,
        headers,
        {
            "resource": "product",
            "product_id": product["id"],
            "valid_from": "2026-01-01",
            "dzd_per_unit": "1200",
        },
    )
    costs = client.get(f"/v1/blocks/{block_id}/costs", headers=headers, params={"season": 2026})
    assert D(str(costs.json()["total_dzd"])) == D("2700")
    assert costs.json()["missing_prices"] == []


def test_irrigation_water_cost(
    client: TestClient,
    db: Session,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm, headers, _user = _owner(make_user, make_farm, auth_header, "cost-water@agrect.app")
    block = _ops_block(client, farm, headers, name="Water")
    block_id = str(block["id"])
    valve_a, valve_b = _valve_ids(db, block_id)
    ready = client.put(
        f"/v1/blocks/{block_id}/irrigation-settings",
        headers=headers,
        json={"efficiency": "1", "kc_source": "entered"},
    )
    assert ready.status_code == 200, ready.text
    _price(
        client,
        farm,
        headers,
        {"resource": "water_m3", "valid_from": "2026-01-01", "dzd_per_unit": "5"},
    )

    logged = client.post(
        f"/v1/blocks/{block_id}/irrigation-events",
        headers=headers,
        json={
            "valve_ids": [valve_a, valve_b],
            "start_at": "2026-08-01T10:00:00+00:00",
            "duration_min": 120,
        },
    )
    assert logged.status_code == 200, logged.text
    assert D(str(logged.json()["volume_m3"])) == D("60")

    costs = client.get(f"/v1/blocks/{block_id}/costs", headers=headers, params={"season": 2026})
    assert costs.status_code == 200, costs.text
    body = costs.json()
    assert D(str(body["by_source"]["water"])) == D("300")
    assert D(str(body["total_dzd"])) == D("300")

    # Delete the event -> water cost line is removed.
    removed = client.delete(
        f"/v1/blocks/{block_id}/irrigation-events/{logged.json()['id']}",
        headers={**headers, "If-Match": str(logged.json()["version"])},
    )
    assert removed.status_code == 204
    costs = client.get(f"/v1/blocks/{block_id}/costs", headers=headers, params={"season": 2026})
    assert D(str(costs.json()["total_dzd"])) == D("0")


def test_stock_moves_purchase_adjustment_and_rules(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm, headers, _user = _owner(make_user, make_farm, auth_header, "cost-stock@agrect.app")
    block = _ops_block(client, farm, headers, name="Stock")
    block_id = str(block["id"])
    product = _product(client, farm, headers, name="Stock fungicide")

    purchase = client.post(
        f"/v1/farms/{farm.id}/stock-moves",
        headers=headers,
        json={
            "product_id": product["id"],
            "date": "2026-07-01",
            "qty": "10",
            "kind": "purchase",
        },
    )
    assert purchase.status_code == 201, purchase.text
    adjust = client.post(
        f"/v1/farms/{farm.id}/stock-moves",
        headers=headers,
        json={
            "product_id": product["id"],
            "date": "2026-07-05",
            "qty": "-2",
            "kind": "adjustment",
        },
    )
    assert adjust.status_code == 201, adjust.text

    bad = client.post(
        f"/v1/farms/{farm.id}/stock-moves",
        headers=headers,
        json={"product_id": product["id"], "date": "2026-07-06", "qty": "1", "kind": "use"},
    )
    assert bad.status_code == 422
    assert bad.json()["fields"]["kind"] == "inputs.move_kind_not_allowed"

    item = _stock_item(client, farm, headers, str(product["id"]))
    assert D(str(item["on_hand"])) == D("8")
    assert item["last_purchase"] == "2026-07-01"

    # A use move (from an operation) cannot be deleted directly.
    _treatment(client, farm, headers, block_id, str(product["id"]), "1")
    moves = client.get(f"/v1/farms/{farm.id}/stock-moves", headers=headers)
    assert moves.status_code == 200
    use_move = next(m for m in moves.json()["moves"] if m["kind"] == "use")
    blocked = client.delete(f"/v1/stock-moves/{use_move['id']}", headers=headers)
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "inputs.use_not_deletable"

    # A purchase move can be deleted.
    ok = client.delete(f"/v1/stock-moves/{purchase.json()['id']}", headers=headers)
    assert ok.status_code == 204
    item = _stock_item(client, farm, headers, str(product["id"]))
    assert D(str(item["on_hand"])) == D("-3")  # -2 adjustment, -1 use


def test_inputs_scoping_404(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm_a, headers_a, _ua = _owner(make_user, make_farm, auth_header, "cost-a@agrect.app")
    _farm_b, headers_b, _ub = _owner(make_user, make_farm, auth_header, "cost-b@agrect.app")
    block = _ops_block(client, farm_a, headers_a, name="Scoped")
    block_id = str(block["id"])
    product = _product(client, farm_a, headers_a, name="Scoped fungicide")
    price = _price(
        client,
        farm_a,
        headers_a,
        {
            "resource": "product",
            "product_id": product["id"],
            "valid_from": "2026-01-01",
            "dzd_per_unit": "1200",
        },
    )
    move = client.post(
        f"/v1/farms/{farm_a.id}/stock-moves",
        headers=headers_a,
        json={"product_id": product["id"], "date": "2026-07-01", "qty": "5", "kind": "purchase"},
    )
    assert move.status_code == 201

    assert client.get(f"/v1/farms/{farm_a.id}/prices", headers=headers_b).status_code == 404
    assert client.get(f"/v1/farms/{farm_a.id}/stock", headers=headers_b).status_code == 404
    assert client.get(f"/v1/farms/{farm_a.id}/costs", headers=headers_b).status_code == 404
    assert client.get(f"/v1/blocks/{block_id}/costs", headers=headers_b).status_code == 404
    assert (
        client.patch(
            f"/v1/prices/{price['id']}", headers=headers_b, json={"dzd_per_unit": "9"}
        ).status_code
        == 404
    )
    assert client.delete(f"/v1/prices/{price['id']}", headers=headers_b).status_code == 404
    assert (
        client.delete(f"/v1/stock-moves/{move.json()['id']}", headers=headers_b).status_code == 404
    )


def _mismatch_op(
    client: TestClient, farm: Farm, headers: dict[str, str], block_id: str, product_id: str
) -> dict[str, object]:
    created = client.post(
        f"/v1/farms/{farm.id}/operations",
        headers=headers,
        json={
            "block_id": block_id,
            "type": "crop_protection_spray",
            "date": "2026-08-01",
            "products": [
                {
                    "product_id": product_id,
                    "rate": "2",
                    "rate_unit": "kg",
                    "rate_basis": "per_block",
                }
            ],
        },
    )
    assert created.status_code == 201, created.text
    return created.json()


def test_unit_mismatch_is_surfaced_never_silent(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm, headers, _user = _owner(make_user, make_farm, auth_header, "cost-mismatch@agrect.app")
    block = _ops_block(client, farm, headers, name="Mismatch")
    block_id = str(block["id"])
    product = _product(client, farm, headers, name="Litre product", unit="l")

    op = _mismatch_op(client, farm, headers, block_id, str(product["id"]))
    assert op["warnings"] == [{"code": "inputs.unit_mismatch", "product": "Litre product"}]
    assert op["cost_dzd"] is None

    item = _stock_item(client, farm, headers, str(product["id"]))
    assert D(str(item["on_hand"])) == D("0")
    assert item["unit_mismatch_count"] == 1

    costs = client.get(f"/v1/blocks/{block_id}/costs", headers=headers, params={"season": 2026})
    body = costs.json()
    assert D(str(body["total_dzd"])) == D("0")
    assert body["missing_prices"] == []
    assert len(body["unit_mismatches"]) == 1
    mm = body["unit_mismatches"][0]
    assert mm["operation_id"] == op["id"]
    assert mm["block_id"] == block_id
    assert mm["block_name"] == "Mismatch"
    assert mm["product"] == "Litre product"
    assert mm["operation_unit"] == "kg"
    assert mm["product_unit"] == "l"

    farm_costs = client.get(f"/v1/farms/{farm.id}/costs", headers=headers, params={"season": 2026})
    farm_mm = farm_costs.json()["unit_mismatches"]
    assert len(farm_mm) == 1
    assert farm_mm[0]["block_id"] == block_id
    assert farm_mm[0]["block_name"] == "Mismatch"


def test_cost_dzd_on_operation_and_journal(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm, headers, _user = _owner(make_user, make_farm, auth_header, "cost-dzd@agrect.app")
    block = _ops_block(client, farm, headers, name="CostDzd")
    block_id = str(block["id"])
    product = _product(client, farm, headers, name="Priced fungicide")
    _price(
        client,
        farm,
        headers,
        {
            "resource": "product",
            "product_id": product["id"],
            "valid_from": "2026-01-01",
            "dzd_per_unit": "1200",
        },
    )
    op = _treatment(client, farm, headers, block_id, str(product["id"]), "2.25")

    got = client.get(f"/v1/operations/{op['id']}", headers=headers)
    assert got.status_code == 200, got.text
    assert D(str(got.json()["cost_dzd"])) == D("2700")
    assert got.json()["warnings"] == []

    journal = client.get(f"/v1/blocks/{block_id}/journal", headers=headers)
    op_item = next(i for i in journal.json()["items"] if i["kind"] == "operation")
    assert D(str(op_item["cost_dzd"])) == D("2700")


def test_price_requires_if_match_and_reason_and_recomputes(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm, headers, _user = _owner(make_user, make_farm, auth_header, "cost-ver@agrect.app")
    block = _ops_block(client, farm, headers, name="Version")
    block_id = str(block["id"])
    product = _product(client, farm, headers, name="Versioned fungicide")
    purchase = client.post(
        f"/v1/farms/{farm.id}/stock-moves",
        headers=headers,
        json={"product_id": product["id"], "date": "2026-07-01", "qty": "10", "kind": "purchase"},
    )
    assert purchase.status_code == 201
    price = _price(
        client,
        farm,
        headers,
        {
            "resource": "product",
            "product_id": product["id"],
            "valid_from": "2026-01-01",
            "dzd_per_unit": "1200",
        },
    )
    assert price["version"] == 1
    _treatment(client, farm, headers, block_id, str(product["id"]), "2.25")

    # Purchase 10 L then use 2.25 L -> 7.75 L on hand.
    item = _stock_item(client, farm, headers, str(product["id"]))
    assert D(str(item["on_hand"])) == D("7.75")

    url = f"/v1/prices/{price['id']}"
    # No If-Match -> 428.
    assert (
        client.patch(url, headers=headers, json={"dzd_per_unit": "1000", "reason": "x"}).status_code
        == 428
    )
    # Wrong If-Match -> 409.
    assert (
        client.patch(
            url,
            headers={**headers, "If-Match": "99"},
            json={"dzd_per_unit": "1000", "reason": "x"},
        ).status_code
        == 409
    )
    # Missing reason -> 422.
    no_reason = client.patch(
        url, headers={**headers, "If-Match": "1"}, json={"dzd_per_unit": "1000"}
    )
    assert no_reason.status_code == 422
    assert no_reason.json()["fields"]["reason"] == "record.reason_required"
    # Valid change -> version bumps and costs recompute to 2 250.
    ok = client.patch(
        url,
        headers={**headers, "If-Match": "1"},
        json={"dzd_per_unit": "1000", "reason": "market drop"},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["version"] == 2
    costs = client.get(f"/v1/blocks/{block_id}/costs", headers=headers, params={"season": 2026})
    assert D(str(costs.json()["total_dzd"])) == D("2250")

    # Delete needs If-Match and reason; then costs clear and the product is missing a price.
    assert client.delete(url, headers={**headers, "If-Match": "2"}).status_code == 422
    assert client.delete(url, headers=headers, params={"reason": "stop"}).status_code == 428
    gone = client.delete(url, headers={**headers, "If-Match": "2"}, params={"reason": "stop"})
    assert gone.status_code == 204
    costs = client.get(f"/v1/blocks/{block_id}/costs", headers=headers, params={"season": 2026})
    assert D(str(costs.json()["total_dzd"])) == D("0")
    assert costs.json()["missing_prices"] == ["Versioned fungicide"]
