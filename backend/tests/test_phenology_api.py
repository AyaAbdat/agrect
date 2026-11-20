import uuid
from collections.abc import Callable
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.auth.models import AppUser
from app.modules.catalog.loader import load_catalog
from app.modules.catalog.models import FarmStagePref
from app.modules.farms.models import Farm
from app.modules.registry.models import RecordVersion

_OLIVE = [
    "00",
    "07",
    "51",
    "55",
    "61",
    "65",
    "69",
    "81",
    "89",
]
_OLIVE_EN = [
    "Winter dormancy",
    "Beginning of shoot development",
    "Inflorescence buds start to swell",
    "Inflorescence expanding",
    "Beginning of flowering",
    "Full flowering",
    "End of flowering, fruit set",
    "Beginning of fruit colouring",
    "Harvest ripeness",
]


def _crop_id(client: TestClient, headers: dict[str, str], code: str) -> str:
    crops = client.get("/v1/catalog/crops", headers=headers)
    assert crops.status_code == 200
    return str(next(row["id"] for row in crops.json() if row["code"] == code))


@pytest.fixture(autouse=True)
def _loaded_catalog() -> None:
    load_catalog()


def test_olive_stages_sorted(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    user = make_user("phenology@agrect.app", "phenology-password")
    headers = auth_header(user)
    olive_id = _crop_id(client, headers, "olive")
    response = client.get(f"/v1/catalog/crops/{olive_id}/stages", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["scale"] == "bbch_olive"
    assert "Sanz-Cortés" in body["scale_citation"]
    assert "2002" in body["scale_citation"]
    stages = body["stages"]
    assert [row["code"] for row in stages] == _OLIVE
    assert [row["name"]["en"] for row in stages] == _OLIVE_EN
    assert [row["sort"] for row in stages] == list(range(1, 10))
    first = stages[0]
    assert first["name"]["fr"] != first["name"]["en"]
    assert first["name"]["ar"] != first["name"]["en"]
    assert set(first["description"]) == {"fr", "ar", "en"}
    assert all(first["description"].values())


def test_stage_dd_empty_then_entered(
    client: TestClient,
    db: Session,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    user = make_user("phenology@agrect.app", "phenology-password")
    farm = make_farm(user, "Phenology", Decimal("36.7"), Decimal("3.1"))
    headers = auth_header(user)
    olive_id = _crop_id(client, headers, "olive")
    stages = client.get(f"/v1/catalog/crops/{olive_id}/stages", headers=headers).json()["stages"]
    target = stages[6]
    empty = client.get(
        f"/v1/farms/{farm.id}/stage-dd",
        headers=headers,
        params={"crop_id": olive_id},
    )
    assert empty.status_code == 200
    empty_body = empty.json()
    assert empty_body["crop_id"] == olive_id
    assert [row["code"] for row in empty_body["stages"]] == _OLIVE
    assert all(row["label"] == "not_enough_data" for row in empty_body["stages"])
    assert all(row["dd_value"] is None for row in empty_body["stages"])
    assert all(row["source"] is None for row in empty_body["stages"])

    saved = client.put(
        f"/v1/farms/{farm.id}/stage-dd",
        headers=headers,
        json={
            "crop_id": olive_id,
            "items": [
                {
                    "stage_def_id": target["id"],
                    "dd_value": "120.5",
                    "base_c": "10",
                    "method": "average",
                    "note": "counted on this farm",
                }
            ],
        },
    )
    assert saved.status_code == 200
    by_id = {row["stage_def_id"]: row for row in saved.json()["stages"]}
    entered = by_id[target["id"]]
    assert entered["dd_value"] == "120.5"
    assert entered["base_c"] == "10"
    assert entered["upper_c"] is None
    assert entered["method"] == "average"
    assert entered["source"] == "entered"
    assert entered["citation"] is None
    assert entered["label"] is None
    others = [row for key, row in by_id.items() if key != target["id"]]
    assert all(row["label"] == "not_enough_data" for row in others)

    again = client.get(
        f"/v1/farms/{farm.id}/stage-dd",
        headers=headers,
        params={"crop_id": olive_id},
    )
    assert again.status_code == 200
    assert again.json() == saved.json()

    history = db.scalars(select(RecordVersion).where(RecordVersion.entity_type == "stage_dd")).all()
    assert len(history) == 1
    assert history[0].farm_id == farm.id
    assert history[0].entity_id == uuid.UUID(olive_id)
    assert history[0].version == 1
    assert history[0].reason == "counted on this farm"
    assert history[0].changed_fields == [target["code"]]
    assert history[0].user_id == user.id

    cleared = client.put(
        f"/v1/farms/{farm.id}/stage-dd",
        headers=headers,
        json={"crop_id": olive_id, "items": []},
    )
    assert cleared.status_code == 200
    assert all(row["label"] == "not_enough_data" for row in cleared.json()["stages"])


def test_base_mismatch_and_positive_dd(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    user = make_user("phenology@agrect.app", "phenology-password")
    farm = make_farm(user, "Phenology", Decimal("36.7"), Decimal("3.1"))
    headers = auth_header(user)
    apple_id = _crop_id(client, headers, "apple")
    stage_id = client.get(f"/v1/catalog/crops/{apple_id}/stages", headers=headers).json()["stages"][
        0
    ]["id"]
    setting = client.put(
        f"/v1/farms/{farm.id}/gdd-settings/{apple_id}",
        headers=headers,
        json={"base_c": "10", "upper_c": None, "method": "average", "start_date": None},
    )
    assert setting.status_code == 200
    mismatch = client.put(
        f"/v1/farms/{farm.id}/stage-dd",
        headers=headers,
        json={
            "crop_id": apple_id,
            "items": [
                {
                    "stage_def_id": stage_id,
                    "dd_value": "80",
                    "base_c": "4",
                    "method": "average",
                }
            ],
        },
    )
    assert mismatch.status_code == 422
    assert mismatch.json()["fields"]["items.0.base_c"] == "phenology.base_mismatch"
    unchanged = client.get(
        f"/v1/farms/{farm.id}/stage-dd",
        headers=headers,
        params={"crop_id": apple_id},
    )
    assert all(row["label"] == "not_enough_data" for row in unchanged.json()["stages"])

    zero = client.put(
        f"/v1/farms/{farm.id}/stage-dd",
        headers=headers,
        json={
            "crop_id": apple_id,
            "items": [
                {
                    "stage_def_id": stage_id,
                    "dd_value": "0",
                    "base_c": "10",
                    "method": "average",
                }
            ],
        },
    )
    assert zero.status_code == 422
    assert zero.json()["fields"]["items.0.dd_value"] == "phenology.dd_must_be_positive"

    matched = client.put(
        f"/v1/farms/{farm.id}/stage-dd",
        headers=headers,
        json={
            "crop_id": apple_id,
            "items": [
                {
                    "stage_def_id": stage_id,
                    "dd_value": "80",
                    "base_c": "10",
                    "method": "single_sine",
                }
            ],
        },
    )
    assert matched.status_code == 200
    row = matched.json()["stages"][0]
    assert row["source"] == "entered"
    assert row["dd_value"] == "80"
    assert row["base_c"] == "10"
    assert row["method"] == "single_sine"


def test_other_user_stage_dd_is_not_found(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    owner = make_user("owner@agrect.app", "password-owner")
    other = make_user("other@agrect.app", "password-other")
    farm = make_farm(owner, "Owner farm", Decimal("36.1"), Decimal("2.2"))
    headers = auth_header(owner)
    other_headers = auth_header(other)
    olive_id = _crop_id(client, headers, "olive")
    stage_id = client.get(f"/v1/catalog/crops/{olive_id}/stages", headers=headers).json()["stages"][
        0
    ]["id"]
    for method in ("get", "put"):
        kwargs: dict[str, object] = {"headers": other_headers}
        if method == "get":
            kwargs["params"] = {"crop_id": olive_id}
        else:
            kwargs["json"] = {
                "crop_id": olive_id,
                "items": [
                    {
                        "stage_def_id": stage_id,
                        "dd_value": "40",
                        "base_c": "10",
                        "method": "average",
                    }
                ],
            }
        response = getattr(client, method)(f"/v1/farms/{farm.id}/stage-dd", **kwargs)
        assert response.status_code == 404
        assert response.json() == {"code": "farm.not_found"}


def test_stage_prefs_round_trip(
    client: TestClient,
    db: Session,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    user = make_user("phenology@agrect.app", "phenology-password")
    farm = make_farm(user, "Phenology", Decimal("36.7"), Decimal("3.1"))
    headers = auth_header(user)
    wheat_id = _crop_id(client, headers, "wheat")
    stage_id = client.get(f"/v1/catalog/crops/{wheat_id}/stages", headers=headers).json()["stages"][
        4
    ]["id"]
    saved = client.put(
        f"/v1/farms/{farm.id}/stage-prefs",
        headers=headers,
        json={"items": [{"stage_def_id": stage_id, "hidden": True, "local_name": "  feuille  "}]},
    )
    assert saved.status_code == 200
    assert saved.json() == {
        "items": [{"stage_def_id": stage_id, "hidden": True, "local_name": "feuille"}]
    }
    read = client.get(
        f"/v1/farms/{farm.id}/stage-prefs",
        headers=headers,
        params={"crop_id": wheat_id},
    )
    assert read.status_code == 200
    assert read.json() == saved.json()
    row = db.scalar(select(FarmStagePref).where(FarmStagePref.farm_id == farm.id))
    assert row is not None
    assert row.hidden is True
    assert row.local_name == "feuille"
    assert str(row.stage_def_id) == stage_id
