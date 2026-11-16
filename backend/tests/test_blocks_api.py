import uuid
from collections.abc import Callable
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.auth.models import AppUser
from app.modules.catalog.loader import load_catalog
from app.modules.farms.models import Farm
from app.modules.registry.models import Block, BlockStatus


def _owner(
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
    email: str = "blocks@agrect.app",
) -> tuple[AppUser, Farm, dict[str, str]]:
    user = make_user(email, "blocks-password")
    farm = make_farm(user, "Farm", Decimal("36"), Decimal("3"))
    return user, farm, auth_header(user)


def test_draft_with_only_a_name(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    _user, farm, headers = _owner(make_user, make_farm, auth_header)
    response = client.post(f"/v1/farms/{farm.id}/blocks", headers=headers, json={"name": "North"})
    assert response.status_code == 201
    body = response.json()
    assert response.headers["etag"] == "1"
    assert body["name"] == "North"
    assert body["status"] == "draft"
    assert body["version"] == 1
    assert body["crop"] is None
    assert body["gross_area_ha"] is None
    assert body["net_area_ha"] is None
    assert body["row_bearing_deg"] is None
    assert body["outline"] is None
    assert body["row_line"] is None
    assert body["sources"] == {
        "gross_area_ha": "calculated",
        "row_bearing_deg": "calculated",
        "net_area_ha": "entered",
    }
    history = client.get(f"/v1/blocks/{body['id']}/history", headers=headers)
    assert history.status_code == 200
    assert history.json() == []
    listed = client.get(f"/v1/farms/{farm.id}/blocks", headers=headers)
    assert listed.status_code == 200
    assert [row["name"] for row in listed.json()] == ["North"]
    assert listed.json()[0]["outline"] is None


def test_duplicate_name(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    _user, farm, headers = _owner(make_user, make_farm, auth_header)
    first = client.post(f"/v1/farms/{farm.id}/blocks", headers=headers, json={"name": "North"})
    assert first.status_code == 201
    second = client.post(f"/v1/farms/{farm.id}/blocks", headers=headers, json={"name": "North"})
    assert second.status_code == 422
    assert second.json() == {"code": "validation_error", "fields": {"name": "block.name_taken"}}
    listed = client.get(f"/v1/farms/{farm.id}/blocks", headers=headers)
    assert [row["name"] for row in listed.json()] == ["North"]


def test_patch_version_and_history(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    user, farm, headers = _owner(make_user, make_farm, auth_header)
    created = client.post(f"/v1/farms/{farm.id}/blocks", headers=headers, json={"name": "North"})
    assert created.status_code == 201
    block_id = created.json()["id"]
    missing = client.patch(f"/v1/blocks/{block_id}", headers=headers, json={"name": "South"})
    assert missing.status_code == 428
    assert missing.json() == {"code": "conflict.version_required"}
    stale = client.patch(
        f"/v1/blocks/{block_id}",
        headers={**headers, "If-Match": "0"},
        json={"name": "South"},
    )
    assert stale.status_code == 409
    assert stale.json() == {"code": "conflict.version"}
    patched = client.patch(
        f"/v1/blocks/{block_id}",
        headers={**headers, "If-Match": "1"},
        json={"name": "South"},
    )
    assert patched.status_code == 200
    assert patched.json()["version"] == 2
    assert patched.json()["name"] == "South"
    assert patched.headers["etag"] == "2"
    history = client.get(f"/v1/blocks/{block_id}/history", headers=headers)
    assert history.status_code == 200
    rows = history.json()
    assert len(rows) == 1
    assert rows[0]["changed_fields"] == ["name"]
    assert rows[0]["version"] == 2
    assert rows[0]["reason"] is None
    assert rows[0]["user_id"] == str(user.id)
    assert rows[0]["entity_type"] == "block"
    again = client.patch(
        f"/v1/blocks/{block_id}",
        headers={**headers, "If-Match": "1"},
        json={"name": "East"},
    )
    assert again.status_code == 409
    assert again.json() == {"code": "conflict.version"}


def test_complete_block_requires_reason(
    client: TestClient,
    db: Session,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    user, farm, headers = _owner(make_user, make_farm, auth_header)
    created = client.post(f"/v1/farms/{farm.id}/blocks", headers=headers, json={"name": "North"})
    block_id = uuid.UUID(created.json()["id"])
    stored = db.get(Block, block_id)
    assert stored is not None
    assert stored.version == 1
    stored.status = BlockStatus.complete
    db.commit()

    missing = client.patch(
        f"/v1/blocks/{block_id}",
        headers={**headers, "If-Match": "1"},
        json={"name": "South"},
    )
    assert missing.status_code == 422
    assert missing.json() == {
        "code": "validation_error",
        "fields": {"reason": "record.reason_required"},
    }
    patched = client.patch(
        f"/v1/blocks/{block_id}",
        headers={**headers, "If-Match": "1"},
        json={"name": "South", "reason": "correct the name"},
    )
    assert patched.status_code == 200
    assert patched.json()["version"] == 2
    assert patched.json()["name"] == "South"
    history = client.get(f"/v1/blocks/{block_id}/history", headers=headers)
    rows = history.json()
    assert len(rows) == 1
    assert rows[0]["reason"] == "correct the name"
    assert rows[0]["changed_fields"] == ["name"]
    assert rows[0]["user_id"] == str(user.id)


def test_other_farm_user_cannot_read_or_edit(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    _user_a, farm_a, headers_a = _owner(make_user, make_farm, auth_header, "a@agrect.app")
    user_b = make_user("b@agrect.app", "password-b")
    headers_b = auth_header(user_b)
    created = client.post(
        f"/v1/farms/{farm_a.id}/blocks",
        headers=headers_a,
        json={"name": "North"},
    )
    block_id = created.json()["id"]
    foreign_get = client.get(f"/v1/blocks/{block_id}", headers=headers_b)
    assert foreign_get.status_code == 404
    assert foreign_get.json() == {"code": "block.not_found"}
    foreign_patch = client.patch(
        f"/v1/blocks/{block_id}",
        headers={**headers_b, "If-Match": "1"},
        json={"name": "Stolen"},
    )
    assert foreign_patch.status_code == 404
    assert foreign_patch.json() == {"code": "block.not_found"}
    foreign_list = client.get(f"/v1/farms/{farm_a.id}/blocks", headers=headers_b)
    assert foreign_list.status_code == 404
    assert foreign_list.json() == {"code": "farm.not_found"}
    missing = client.get(f"/v1/blocks/{uuid.uuid4()}", headers=headers_a)
    assert missing.status_code == 404
    assert missing.json() == {"code": "block.not_found"}


def test_archive_hides_block_unless_included(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    _user, farm, headers = _owner(make_user, make_farm, auth_header)
    alpha = client.post(f"/v1/farms/{farm.id}/blocks", headers=headers, json={"name": "Alpha"})
    bravo = client.post(f"/v1/farms/{farm.id}/blocks", headers=headers, json={"name": "Bravo"})
    assert alpha.status_code == 201
    assert bravo.status_code == 201
    alpha_id = alpha.json()["id"]
    missing = client.post(f"/v1/blocks/{alpha_id}/archive", headers=headers)
    assert missing.status_code == 428
    assert missing.json() == {"code": "conflict.version_required"}
    archived = client.post(
        f"/v1/blocks/{alpha_id}/archive",
        headers={**headers, "If-Match": "1"},
    )
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"
    assert archived.json()["version"] == 2
    assert archived.headers["etag"] == "2"
    listed = client.get(f"/v1/farms/{farm.id}/blocks", headers=headers)
    assert [row["name"] for row in listed.json()] == ["Bravo"]
    included = client.get(
        f"/v1/farms/{farm.id}/blocks",
        headers=headers,
        params={"include_archived": "true"},
    )
    body = included.json()
    assert [row["name"] for row in body] == ["Alpha", "Bravo"]
    assert body[0]["status"] == "archived"
    assert body[1]["status"] == "draft"
    history = client.get(f"/v1/blocks/{alpha_id}/history", headers=headers)
    assert history.json()[0]["changed_fields"] == ["status"]
    assert history.json()[0]["version"] == 2


def test_crop_and_training_system(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    load_catalog()
    _user, farm, headers = _owner(make_user, make_farm, auth_header)
    crops = client.get("/v1/catalog/crops", headers=headers).json()
    grape = next(row for row in crops if row["code"] == "table_grape")
    apple = next(row for row in crops if row["code"] == "apple")
    systems = client.get(
        f"/v1/catalog/crops/{grape['id']}/training-systems",
        headers=headers,
    ).json()
    vsp = next(row for row in systems if row["code"] == "vsp")
    mismatch = client.post(
        f"/v1/farms/{farm.id}/blocks",
        headers=headers,
        json={"name": "Mismatch", "crop_id": apple["id"], "training_system_id": vsp["id"]},
    )
    assert mismatch.status_code == 422
    assert mismatch.json()["fields"]["training_system_id"] == "block.training_system_mismatch"
    unknown_crop = client.post(
        f"/v1/farms/{farm.id}/blocks",
        headers=headers,
        json={"name": "Missing crop", "crop_id": str(uuid.uuid4())},
    )
    assert unknown_crop.status_code == 422
    assert unknown_crop.json() == {
        "code": "validation_error",
        "fields": {"crop_id": "catalog.crop_not_found"},
    }
    created = client.post(
        f"/v1/farms/{farm.id}/blocks",
        headers=headers,
        json={"name": "Vine", "crop_id": grape["id"], "training_system_id": vsp["id"]},
    )
    assert created.status_code == 201
    assert created.json()["crop"]["code"] == "table_grape"
    assert created.json()["training_system_id"] == vsp["id"]
    listed = client.get(f"/v1/farms/{farm.id}/blocks", headers=headers)
    assert listed.json()[0]["crop"] == {
        "id": grape["id"],
        "code": "table_grape",
        "name": grape["name"],
    }
