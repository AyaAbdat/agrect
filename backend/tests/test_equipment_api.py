"""Equipment API: machines, use per operation, costs, engine hours, maintenance, scoping."""

from collections.abc import Callable
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from app.modules.auth.models import AppUser
from app.modules.farms.models import Farm
from tests.test_operations_api import _ops_block, _owner
from tests.vectors import D


def _machine(
    client: TestClient,
    farm: Farm,
    headers: dict[str, str],
    name: str = "Tractor 1",
    **extra: object,
) -> dict[str, object]:
    created = client.post(
        f"/v1/farms/{farm.id}/machines",
        headers=headers,
        json={"type": "tractor", "name": name, **extra},
    )
    assert created.status_code == 201, created.text
    return created.json()


def _price(client: TestClient, farm: Farm, headers: dict[str, str], resource: str, dzd: str):
    created = client.post(
        f"/v1/farms/{farm.id}/prices",
        headers=headers,
        json={"resource": resource, "valid_from": "2026-01-01", "dzd_per_unit": dzd},
    )
    assert created.status_code == 201, created.text


def _tillage(
    client: TestClient,
    farm: Farm,
    headers: dict[str, str],
    block_id: str,
    machines: list[dict[str, object]],
    on: str = "2026-03-10",
):
    return client.post(
        f"/v1/farms/{farm.id}/operations",
        headers=headers,
        json={"block_id": block_id, "type": "tillage", "date": on, "machines": machines},
    )


def test_machine_use_work_rate_and_costs(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm, headers, _user = _owner(make_user, make_farm, auth_header, "eq-cost@agrect.app")
    block_id = str(_ops_block(client, farm, headers)["id"])
    machine = _machine(client, farm, headers)
    _price(client, farm, headers, "machine_h", "900")
    _price(client, farm, headers, "fuel_l", "45")

    created = _tillage(
        client,
        farm,
        headers,
        block_id,
        [{"machine_id": machine["id"], "hours": "2", "fuel_l": "10"}],
    )
    assert created.status_code == 201, created.text
    op = created.json()
    assert len(op["machines"]) == 1
    use = op["machines"][0]
    assert use["id"] == machine["id"]
    assert use["name"] == "Tractor 1"
    assert D(str(use["hours"])) == D("2")
    assert D(str(use["fuel_l"])) == D("10")
    assert D(str(use["work_rate_ha_h"])) == D("0.75")
    assert D(str(op["cost_dzd"])) == D("2250")
    assert op["warnings"] == []

    costs = client.get(f"/v1/blocks/{block_id}/costs", headers=headers, params={"season": 2026})
    body = costs.json()
    assert D(str(body["by_source"]["machine"])) == D("1800")
    assert D(str(body["by_source"]["fuel"])) == D("450")
    assert body["missing_prices"] == []

    # Editing the use replaces the lines.
    edited = client.patch(
        f"/v1/operations/{op['id']}",
        headers={**headers, "If-Match": str(op["version"])},
        json={"machines": [{"machine_id": machine["id"], "hours": "1"}]},
    )
    assert edited.status_code == 200, edited.text
    assert D(str(edited.json()["cost_dzd"])) == D("900")
    assert edited.json()["machines"][0]["fuel_l"] is None

    cleared = client.patch(
        f"/v1/operations/{op['id']}",
        headers={**headers, "If-Match": str(edited.json()["version"])},
        json={"machines": []},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["machines"] == []
    assert cleared.json()["cost_dzd"] is None


def test_missing_resource_prices_listed(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm, headers, _user = _owner(make_user, make_farm, auth_header, "eq-missing@agrect.app")
    block_id = str(_ops_block(client, farm, headers)["id"])
    machine = _machine(client, farm, headers)
    worker = client.post(
        f"/v1/farms/{farm.id}/workers",
        headers=headers,
        json={"name": "Ali", "role": "operator", "kind": "seasonal"},
    ).json()
    created = client.post(
        f"/v1/farms/{farm.id}/operations",
        headers=headers,
        json={
            "block_id": block_id,
            "type": "tillage",
            "date": "2026-03-10",
            "labour": {"worker_ids": [worker["id"]], "hours_each": "6"},
            "machines": [{"machine_id": machine["id"], "hours": "2", "fuel_l": "10"}],
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["cost_dzd"] is None

    block_costs = client.get(
        f"/v1/blocks/{block_id}/costs", headers=headers, params={"season": 2026}
    )
    assert block_costs.json()["missing_prices"] == [
        "resource.labour_h",
        "resource.machine_h",
        "resource.fuel_l",
    ]
    farm_costs = client.get(f"/v1/farms/{farm.id}/costs", headers=headers, params={"season": 2026})
    assert farm_costs.json()["missing_prices"] == [
        "resource.labour_h",
        "resource.machine_h",
        "resource.fuel_l",
    ]

    _price(client, farm, headers, "labour_h", "150")
    block_costs = client.get(
        f"/v1/blocks/{block_id}/costs", headers=headers, params={"season": 2026}
    )
    assert block_costs.json()["missing_prices"] == ["resource.machine_h", "resource.fuel_l"]
    assert D(str(block_costs.json()["by_source"]["labour"])) == D("900")


def test_machine_in_repair_warning_and_validation(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm, headers, _user = _owner(make_user, make_farm, auth_header, "eq-repair@agrect.app")
    other, other_headers, _ = _owner(make_user, make_farm, auth_header, "eq-repair2@agrect.app")
    block_id = str(_ops_block(client, farm, headers)["id"])
    machine = _machine(client, farm, headers, status="repair")

    created = _tillage(
        client, farm, headers, block_id, [{"machine_id": machine["id"], "hours": "2"}]
    )
    assert created.status_code == 201, created.text
    assert created.json()["warnings"] == [
        {"code": "equipment.machine_in_repair", "machine": "Tractor 1"}
    ]

    zero = _tillage(client, farm, headers, block_id, [{"machine_id": machine["id"], "hours": "0"}])
    assert zero.status_code == 422
    assert zero.json()["fields"]["machines.hours"] == "equipment.hours_invalid"

    foreign = _machine(client, other, other_headers, "Foreign")
    rejected = _tillage(
        client, farm, headers, block_id, [{"machine_id": foreign["id"], "hours": "1"}]
    )
    assert rejected.status_code == 422
    assert rejected.json()["fields"]["machines"] == "equipment.machine_not_in_farm"

    twice = _tillage(
        client,
        farm,
        headers,
        block_id,
        [
            {"machine_id": machine["id"], "hours": "1"},
            {"machine_id": machine["id"], "hours": "1"},
        ],
    )
    assert twice.status_code == 422
    assert twice.json()["fields"]["machines"] == "equipment.machine_duplicate"


def test_machine_crud_and_in_use_guard(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm, headers, _user = _owner(make_user, make_farm, auth_header, "eq-crud@agrect.app")
    machine = _machine(client, farm, headers)
    assert machine["status"] == "ok"
    dup = client.post(
        f"/v1/farms/{farm.id}/machines",
        headers=headers,
        json={"type": "sprayer", "name": "Tractor 1"},
    )
    assert dup.status_code == 422
    assert dup.json()["fields"]["name"] == "equipment.machine_name_taken"

    assert (
        client.patch(f"/v1/machines/{machine['id']}", headers=headers, json={}).status_code == 428
    )
    patched = client.patch(
        f"/v1/machines/{machine['id']}",
        headers={**headers, "If-Match": "1"},
        json={"status": "repair", "type": "sprayer"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["status"] == "repair"
    assert patched.json()["version"] == 2

    block_id = str(_ops_block(client, farm, headers)["id"])
    used = _tillage(client, farm, headers, block_id, [{"machine_id": machine["id"], "hours": "1"}])
    assert used.status_code == 201, used.text
    blocked = client.delete(f"/v1/machines/{machine['id']}", headers={**headers, "If-Match": "2"})
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "equipment.machine_in_use"

    spare = _machine(client, farm, headers, "Spare")
    removed = client.delete(f"/v1/machines/{spare['id']}", headers={**headers, "If-Match": "1"})
    assert removed.status_code == 204
    listed = client.get(f"/v1/farms/{farm.id}/machines", headers=headers)
    assert [row["name"] for row in listed.json()["machines"]] == ["Tractor 1"]


def test_engine_hours_and_maintenance_due(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm, headers, _user = _owner(make_user, make_farm, auth_header, "eq-maint@agrect.app")
    block_id = str(_ops_block(client, farm, headers)["id"])
    machine = _machine(
        client, farm, headers, engine_hours_reading="1000", reading_date="2026-03-01"
    )
    machine_id = str(machine["id"])
    # Before the reading: not counted.
    _tillage(
        client, farm, headers, block_id, [{"machine_id": machine_id, "hours": "5"}], "2026-02-20"
    )
    _tillage(
        client,
        farm,
        headers,
        block_id,
        [{"machine_id": machine_id, "hours": "2", "fuel_l": "10"}],
        "2026-03-10",
    )

    no_interval = client.post(
        f"/v1/machines/{machine_id}/maintenance", headers=headers, json={"task": "Oil"}
    )
    assert no_interval.status_code == 422
    assert no_interval.json()["fields"]["interval_h"] == "equipment.interval_required"

    oil = client.post(
        f"/v1/machines/{machine_id}/maintenance",
        headers=headers,
        json={"task": "Oil change", "interval_h": "250", "last_done_h": "800"},
    )
    assert oil.status_code == 201, oil.text
    today = datetime.now(ZoneInfo("Africa/Algiers")).date()
    filters = client.post(
        f"/v1/machines/{machine_id}/maintenance",
        headers=headers,
        json={
            "task": "Filters",
            "interval_days": 180,
            "last_done_date": (today - timedelta(days=200)).isoformat(),
        },
    )
    assert filters.status_code == 201, filters.text
    assert filters.json()["due"]["due_by_date"] is True
    assert filters.json()["due"]["next_due_date"] == (today - timedelta(days=20)).isoformat()

    detail = client.get(f"/v1/machines/{machine_id}", headers=headers, params={"season": 2026})
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert D(str(body["current_engine_hours"])) == D("1002")
    season = body["uses_this_season"]
    assert season["uses_count"] == 2
    assert D(str(season["hours"])) == D("7")
    assert D(str(season["fuel_l"])) == D("10")
    assert D(str(season["area_ha"])) == D("3.00")
    oil_row = next(row for row in body["maintenance"] if row["task"] == "Oil change")
    assert D(str(oil_row["due"]["next_due_h"])) == D("1050")
    assert oil_row["due"]["due_by_hours"] is False

    due = client.get(f"/v1/farms/{farm.id}/maintenance/due", headers=headers)
    assert [row["task"] for row in due.json()["items"]] == ["Filters"]

    # 58 more hours after the reading -> 1 060 h, past 1 050.
    _tillage(
        client, farm, headers, block_id, [{"machine_id": machine_id, "hours": "58"}], "2026-04-01"
    )
    due = client.get(f"/v1/farms/{farm.id}/maintenance/due", headers=headers)
    rows = {row["task"]: row for row in due.json()["items"]}
    assert set(rows) == {"Filters", "Oil change"}
    assert rows["Oil change"]["due"]["due_by_hours"] is True
    assert rows["Oil change"]["due"]["overdue"] is True

    # Mark done at the current engine hours -> next due 1 310, no longer due.
    done = client.post(
        f"/v1/maintenance/{oil.json()['id']}/done",
        headers={**headers, "If-Match": str(oil.json()["version"])},
        json={"date": today.isoformat()},
    )
    assert done.status_code == 200, done.text
    assert D(str(done.json()["last_done_h"])) == D("1060")
    assert D(str(done.json()["due"]["next_due_h"])) == D("1310")
    assert done.json()["due"]["due_by_hours"] is False

    patched = client.patch(
        f"/v1/maintenance/{filters.json()['id']}",
        headers={**headers, "If-Match": str(filters.json()["version"])},
        json={"interval_days": None},
    )
    assert patched.status_code == 422
    assert patched.json()["fields"]["interval_h"] == "equipment.interval_required"

    listed = client.get(f"/v1/machines/{machine_id}/maintenance", headers=headers)
    assert len(listed.json()["items"]) == 2
    removed = client.delete(
        f"/v1/maintenance/{filters.json()['id']}",
        headers={**headers, "If-Match": str(filters.json()["version"])},
    )
    assert removed.status_code == 204


def test_labour_fixes(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm, headers, _user = _owner(make_user, make_farm, auth_header, "eq-labour@agrect.app")
    block_id = str(_ops_block(client, farm, headers)["id"])
    retired = client.post(
        f"/v1/farms/{farm.id}/workers",
        headers=headers,
        json={"name": "Retired", "role": "operator", "kind": "seasonal", "active": False},
    ).json()

    created = client.post(
        f"/v1/farms/{farm.id}/operations",
        headers=headers,
        json={
            "block_id": block_id,
            "type": "pruning",
            "date": "2026-03-10",
            "labour": {"worker_ids": [retired["id"]], "hours_each": "6"},
        },
    )
    assert created.status_code == 201, created.text
    op = created.json()
    assert op["workers_count"] == 1
    assert op["warnings"] == [{"code": "labour.worker_inactive", "worker": "Retired"}]

    cleared = client.patch(
        f"/v1/operations/{op['id']}",
        headers={**headers, "If-Match": str(op["version"])},
        json={"labour": None},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["labour"] is None
    assert cleared.json()["workers_count"] is None
    assert cleared.json()["warnings"] == []


def test_equipment_scoping_404(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm_a, headers_a, _ = _owner(make_user, make_farm, auth_header, "eq-a@agrect.app")
    _farm_b, headers_b, _ = _owner(make_user, make_farm, auth_header, "eq-b@agrect.app")
    machine = _machine(client, farm_a, headers_a)
    task = client.post(
        f"/v1/machines/{machine['id']}/maintenance",
        headers=headers_a,
        json={"task": "Oil", "interval_h": "250"},
    ).json()
    base = f"/v1/farms/{farm_a.id}"
    mid = machine["id"]
    tid = task["id"]
    match = {**headers_b, "If-Match": "1"}
    assert client.get(f"{base}/machines", headers=headers_b).status_code == 404
    assert (
        client.post(
            f"{base}/machines", headers=headers_b, json={"type": "other", "name": "X"}
        ).status_code
        == 404
    )
    assert client.get(f"{base}/maintenance/due", headers=headers_b).status_code == 404
    assert client.get(f"/v1/machines/{mid}", headers=headers_b).status_code == 404
    assert client.patch(f"/v1/machines/{mid}", headers=match, json={}).status_code == 404
    assert client.delete(f"/v1/machines/{mid}", headers=match).status_code == 404
    assert client.get(f"/v1/machines/{mid}/maintenance", headers=headers_b).status_code == 404
    assert (
        client.post(
            f"/v1/machines/{mid}/maintenance",
            headers=headers_b,
            json={"task": "Oil", "interval_h": "250"},
        ).status_code
        == 404
    )
    assert client.patch(f"/v1/maintenance/{tid}", headers=match, json={}).status_code == 404
    assert (
        client.post(
            f"/v1/maintenance/{tid}/done", headers=match, json={"date": "2026-03-10"}
        ).status_code
        == 404
    )
    assert client.delete(f"/v1/maintenance/{tid}", headers=match).status_code == 404
