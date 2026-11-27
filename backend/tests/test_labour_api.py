"""Labour API: workers, attendance, operation labour, labour cost, norms, scoping."""

from collections.abc import Callable

from fastapi.testclient import TestClient

from app.modules.auth.models import AppUser
from app.modules.farms.models import Farm
from tests.test_blocks_geo import rectangle
from tests.test_operations_api import _crop_id, _ops_block, _owner
from tests.vectors import D


def _worker(
    client: TestClient,
    farm: Farm,
    headers: dict[str, str],
    name: str,
    *,
    role: str = "operator",
    kind: str = "seasonal",
) -> dict[str, object]:
    created = client.post(
        f"/v1/farms/{farm.id}/workers",
        headers=headers,
        json={"name": name, "role": role, "kind": kind},
    )
    assert created.status_code == 201, created.text
    return created.json()


def _pruning(
    client: TestClient,
    farm: Farm,
    headers: dict[str, str],
    block_id: str,
    labour: dict[str, object] | None,
    date: str = "2026-03-10",
):
    body: dict[str, object] = {"block_id": block_id, "type": "pruning", "date": date}
    if labour is not None:
        body["labour"] = labour
    return client.post(f"/v1/farms/{farm.id}/operations", headers=headers, json=body)


def _small_block(client: TestClient, farm: Farm, headers: dict[str, str]) -> str:
    created = client.post(
        f"/v1/farms/{farm.id}/blocks",
        headers=headers,
        json={
            "name": "South",
            "outline": rectangle(36.01, 3.01, 120, 120),
            "net_area_ha": "1.00",
            "crop_id": _crop_id(client, headers),
            "rows_total": 20,
        },
    )
    assert created.status_code == 201, created.text
    return str(created.json()["id"])


def test_worker_crud_and_in_use_guard(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm, headers, _user = _owner(make_user, make_farm, auth_header, "labour-crud@agrect.app")
    worker = _worker(client, farm, headers, "Karim", role="irrigation_lead", kind="permanent")
    assert worker["active"] is True
    assert worker["role"] == "irrigation_lead"
    assert worker["kind"] == "permanent"
    assert worker["version"] == 1

    dup = client.post(
        f"/v1/farms/{farm.id}/workers",
        headers=headers,
        json={"name": "Karim", "role": "operator", "kind": "seasonal"},
    )
    assert dup.status_code == 422
    assert dup.json()["fields"]["name"] == "labour.worker_name_taken"

    no_match = client.patch(f"/v1/workers/{worker['id']}", headers=headers, json={"phone": "x"})
    assert no_match.status_code == 428
    patched = client.patch(
        f"/v1/workers/{worker['id']}",
        headers={**headers, "If-Match": "1"},
        json={"phone": "0550 00 00 00", "role": "operator"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["phone"] == "0550 00 00 00"
    assert patched.json()["version"] == 2

    listed = client.get(f"/v1/farms/{farm.id}/workers", headers=headers)
    assert [row["name"] for row in listed.json()["workers"]] == ["Karim"]

    block = _ops_block(client, farm, headers)
    op = _pruning(
        client, farm, headers, str(block["id"]), {"worker_ids": [worker["id"]], "hours_each": "4"}
    )
    assert op.status_code == 201, op.text

    blocked = client.delete(f"/v1/workers/{worker['id']}", headers={**headers, "If-Match": "2"})
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "labour.worker_in_use"

    retired = client.patch(
        f"/v1/workers/{worker['id']}",
        headers={**headers, "If-Match": "2"},
        json={"active": False},
    )
    assert retired.status_code == 200
    assert retired.json()["active"] is False

    spare = _worker(client, farm, headers, "Spare")
    removed = client.delete(f"/v1/workers/{spare['id']}", headers={**headers, "If-Match": "1"})
    assert removed.status_code == 204
    listed = client.get(f"/v1/farms/{farm.id}/workers", headers=headers)
    assert [row["name"] for row in listed.json()["workers"]] == ["Karim"]


def test_attendance_upsert_and_summary(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm, headers, _user = _owner(make_user, make_farm, auth_header, "labour-att@agrect.app")
    ali = _worker(client, farm, headers, "Ali")
    sara = _worker(client, farm, headers, "Sara")

    first = client.put(
        f"/v1/farms/{farm.id}/attendance",
        headers=headers,
        json={
            "date": "2026-03-10",
            "items": [
                {"worker_id": ali["id"], "present": True, "hours": "8"},
                {"worker_id": sara["id"], "present": False, "note": "sick"},
            ],
        },
    )
    assert first.status_code == 200, first.text
    assert len(first.json()["items"]) == 2

    # Upsert: same day again replaces Ali's row, no duplicate.
    again = client.put(
        f"/v1/farms/{farm.id}/attendance",
        headers=headers,
        json={
            "date": "2026-03-10",
            "items": [{"worker_id": ali["id"], "present": True, "hours": "6"}],
        },
    )
    assert again.status_code == 200, again.text
    day = client.get(
        f"/v1/farms/{farm.id}/attendance", headers=headers, params={"date": "2026-03-10"}
    )
    items = {row["worker_name"]: row for row in day.json()["items"]}
    assert len(items) == 2
    assert D(str(items["Ali"]["hours"])) == D("6")
    assert items["Sara"]["present"] is False
    assert items["Sara"]["note"] == "sick"

    client.put(
        f"/v1/farms/{farm.id}/attendance",
        headers=headers,
        json={
            "date": "2026-03-11",
            "items": [
                {"worker_id": ali["id"], "present": True, "hours": "7.5"},
                {"worker_id": sara["id"], "present": True},
            ],
        },
    )
    summary = client.get(
        f"/v1/farms/{farm.id}/attendance/summary",
        headers=headers,
        params={"from": "2026-03-01", "to": "2026-03-31"},
    )
    assert summary.status_code == 200, summary.text
    rows = {row["worker_name"]: row for row in summary.json()["workers"]}
    assert rows["Ali"]["days_present"] == 2
    assert D(str(rows["Ali"]["hours"])) == D("13.5")
    assert rows["Sara"]["days_present"] == 1
    assert D(str(rows["Sara"]["hours"])) == D("0")


def test_operation_labour_cost_and_edit(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm, headers, _user = _owner(make_user, make_farm, auth_header, "labour-cost@agrect.app")
    block = _ops_block(client, farm, headers)
    block_id = str(block["id"])
    ids = [str(_worker(client, farm, headers, name)["id"]) for name in ("A1", "B2", "C3")]
    price = client.post(
        f"/v1/farms/{farm.id}/prices",
        headers=headers,
        json={"resource": "labour_h", "valid_from": "2026-01-01", "dzd_per_unit": "150"},
    )
    assert price.status_code == 201, price.text

    created = _pruning(client, farm, headers, block_id, {"worker_ids": ids, "hours_each": "6"})
    assert created.status_code == 201, created.text
    op = created.json()
    labour = op["labour"]
    assert [row["name"] for row in labour["workers"]] == ["A1", "B2", "C3"]
    assert labour["headcount"] == 3
    assert D(str(labour["total_hours"])) == D("18")
    assert op["workers_count"] == 3
    assert D(str(op["cost_dzd"])) == D("2700")

    costs = client.get(f"/v1/blocks/{block_id}/costs", headers=headers, params={"season": 2026})
    assert D(str(costs.json()["by_source"]["labour"])) == D("2700")
    farm_costs = client.get(f"/v1/farms/{farm.id}/costs", headers=headers, params={"season": 2026})
    block_row = next(b for b in farm_costs.json()["blocks"] if b["block_id"] == block_id)
    assert D(str(block_row["by_source"]["labour"])) == D("2700")

    # Editing hours replaces the line (no second line).
    edited = client.patch(
        f"/v1/operations/{op['id']}",
        headers={**headers, "If-Match": str(op["version"])},
        json={"labour": {"worker_ids": ids, "hours_each": "4"}},
    )
    assert edited.status_code == 200, edited.text
    assert D(str(edited.json()["labour"]["total_hours"])) == D("12")
    assert D(str(edited.json()["cost_dzd"])) == D("1800")
    costs = client.get(f"/v1/blocks/{block_id}/costs", headers=headers, params={"season": 2026})
    assert D(str(costs.json()["by_source"]["labour"])) == D("1800")
    assert D(str(costs.json()["total_dzd"])) == D("1800")

    # Clearing labour removes the line.
    cleared = client.patch(
        f"/v1/operations/{op['id']}",
        headers={**headers, "If-Match": str(edited.json()["version"])},
        json={"labour": None},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["labour"] is None
    assert cleared.json()["cost_dzd"] is None


def test_labour_without_price_has_no_cost_and_price_recomputes(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm, headers, _user = _owner(make_user, make_farm, auth_header, "labour-late@agrect.app")
    block = _ops_block(client, farm, headers)
    created = _pruning(client, farm, headers, str(block["id"]), {"headcount": 2, "hours_each": "5"})
    assert created.status_code == 201, created.text
    assert D(str(created.json()["labour"]["total_hours"])) == D("10")
    assert created.json()["labour"]["workers"] == []
    assert created.json()["cost_dzd"] is None

    client.post(
        f"/v1/farms/{farm.id}/prices",
        headers=headers,
        json={"resource": "labour_h", "valid_from": "2026-01-01", "dzd_per_unit": "150"},
    )
    fetched = client.get(f"/v1/operations/{created.json()['id']}", headers=headers)
    assert D(str(fetched.json()["cost_dzd"])) == D("1500")


def test_headcount_mismatch_and_foreign_worker(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm, headers, _user = _owner(make_user, make_farm, auth_header, "labour-mis@agrect.app")
    other, other_headers, _ = _owner(make_user, make_farm, auth_header, "labour-mis2@agrect.app")
    block = _ops_block(client, farm, headers)
    ids = [str(_worker(client, farm, headers, name)["id"]) for name in ("A", "B")]

    mismatch = _pruning(
        client,
        farm,
        headers,
        str(block["id"]),
        {"worker_ids": ids, "headcount": 3, "hours_each": "6"},
    )
    assert mismatch.status_code == 422
    assert mismatch.json()["fields"]["labour.headcount"] == "labour.headcount_mismatch"

    foreign = str(_worker(client, other, other_headers, "Foreign")["id"])
    rejected = _pruning(
        client, farm, headers, str(block["id"]), {"worker_ids": [foreign], "hours_each": "6"}
    )
    assert rejected.status_code == 422
    assert rejected.json()["fields"]["labour.worker_ids"] == "labour.worker_not_in_farm"

    empty = _pruning(client, farm, headers, str(block["id"]), {"hours_each": "6"})
    assert empty.status_code == 422
    assert empty.json()["fields"]["labour.headcount"] == "labour.workers_required"


def test_labour_norms(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm, headers, _user = _owner(make_user, make_farm, auth_header, "labour-norm@agrect.app")
    big = str(_ops_block(client, farm, headers)["id"])
    small = _small_block(client, farm, headers)
    first = _pruning(client, farm, headers, big, {"headcount": 3, "hours_each": "6"})
    second = _pruning(client, farm, headers, small, {"headcount": 2, "hours_each": "6"})
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert D(str(first.json()["area_ha"])) == D("1.50")
    assert D(str(second.json()["area_ha"])) == D("1.00")
    # Another season does not count.
    _pruning(client, farm, headers, big, {"headcount": 9, "hours_each": "9"}, date="2025-03-10")

    norms = client.get(
        f"/v1/farms/{farm.id}/labour-norms", headers=headers, params={"season": 2026}
    )
    assert norms.status_code == 200, norms.text
    rows = norms.json()["rows"]
    assert len(rows) == 1
    row = rows[0]
    assert row["operation_type"] == "pruning"
    assert row["crop"]["code"] == "table_grape"
    assert D(str(row["total_hours"])) == D("30")
    assert D(str(row["total_area_ha"])) == D("2.50")
    assert D(str(row["h_per_ha"])) == D("12.0")
    assert row["operations_count"] == 2


def test_labour_scoping_404(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm_a, headers_a, _ = _owner(make_user, make_farm, auth_header, "labour-a@agrect.app")
    _farm_b, headers_b, _ = _owner(make_user, make_farm, auth_header, "labour-b@agrect.app")
    worker = _worker(client, farm_a, headers_a, "Owned")
    base = f"/v1/farms/{farm_a.id}"
    assert client.get(f"{base}/workers", headers=headers_b).status_code == 404
    assert (
        client.post(
            f"{base}/workers",
            headers=headers_b,
            json={"name": "X", "role": "other", "kind": "seasonal"},
        ).status_code
        == 404
    )
    assert (
        client.get(f"{base}/attendance", headers=headers_b, params={"date": "2026-03-10"})
    ).status_code == 404
    assert (
        client.put(
            f"{base}/attendance", headers=headers_b, json={"date": "2026-03-10", "items": []}
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"{base}/attendance/summary",
            headers=headers_b,
            params={"from": "2026-03-01", "to": "2026-03-31"},
        ).status_code
        == 404
    )
    assert client.get(f"{base}/labour-norms", headers=headers_b).status_code == 404
    assert (
        client.patch(
            f"/v1/workers/{worker['id']}",
            headers={**headers_b, "If-Match": "1"},
            json={"phone": "1"},
        ).status_code
        == 404
    )
    assert (
        client.delete(
            f"/v1/workers/{worker['id']}", headers={**headers_b, "If-Match": "1"}
        ).status_code
        == 404
    )
