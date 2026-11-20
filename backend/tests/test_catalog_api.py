import uuid
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from app.modules.auth.models import AppUser
from app.modules.catalog.loader import load_catalog

_FAO56 = (
    "Allen R.G., Pereira L.S., Raes D., Smith M. (1998). Crop evapotranspiration. "
    "FAO Irrigation and Drainage Paper 56, Table 19 (typical soil water characteristics); "
    "typical value = midpoint of the range."
)
_NULL_TEXTURES = {"sandy_clay_loam", "clay_loam", "sandy_clay"}


@pytest.fixture(autouse=True)
def _loaded_catalog() -> None:
    load_catalog()


def test_crops_sorted_with_three_names(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    user = make_user("catalog@agrect.app", "catalog-password")
    response = client.get("/v1/catalog/crops", headers=auth_header(user))
    assert response.status_code == 200
    body = response.json()
    assert [row["code"] for row in body] == [
        "table_grape",
        "apple",
        "olive",
        "wheat",
        "barley",
    ]
    assert body[0]["kind"] == "perennial"
    assert body[0]["name"] == {
        "fr": "Vigne (raisin de table)",
        "ar": "كرمة (عنب المائدة)",
        "en": "Table grape",
    }
    for row in body:
        assert set(row["name"]) == {"fr", "ar", "en"}
        assert all(row["name"].values())


def test_apple_varieties_and_wheat_training_systems(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    user = make_user("catalog@agrect.app", "catalog-password")
    headers = auth_header(user)
    crops = client.get("/v1/catalog/crops", headers=headers).json()
    apple = next(row for row in crops if row["code"] == "apple")
    wheat = next(row for row in crops if row["code"] == "wheat")
    varieties = client.get(f"/v1/catalog/crops/{apple['id']}/varieties", headers=headers)
    training = client.get(f"/v1/catalog/crops/{wheat['id']}/training-systems", headers=headers)
    assert varieties.status_code == 200
    assert {row["name"] for row in varieties.json()} == {
        "Golden Delicious",
        "Gala",
        "Granny Smith",
        "Fuji",
        "Red Delicious",
    }
    assert training.status_code == 200
    assert training.json() == []


def test_soil_textures(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    user = make_user("catalog@agrect.app", "catalog-password")
    response = client.get("/v1/catalog/soil-textures", headers=auth_header(user))
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 12
    loam = next(row for row in body if row["code"] == "loam")
    assert loam["theta_fc_min"] == "0.200"
    assert loam["theta_fc_max"] == "0.300"
    assert loam["theta_wp_min"] == "0.070"
    assert loam["theta_wp_max"] == "0.170"
    assert loam["theta_fc"] == "0.250"
    assert loam["theta_wp"] == "0.120"
    assert loam["citation"] == _FAO56
    assert "Table 19" in loam["citation"]
    assert loam["source"] == "entered"
    clay_loam = next(row for row in body if row["code"] == "clay_loam")
    assert clay_loam["theta_fc_min"] is None
    assert clay_loam["theta_fc_max"] is None
    assert clay_loam["theta_wp_min"] is None
    assert clay_loam["theta_wp_max"] is None
    assert clay_loam["theta_fc"] is None
    assert clay_loam["theta_wp"] is None
    assert clay_loam["citation"] is None
    assert clay_loam["source"] is None
    cited = [row for row in body if row["citation"] is not None]
    empty = [row for row in body if row["citation"] is None]
    assert len(cited) == 9
    assert {row["code"] for row in empty} == _NULL_TEXTURES
    assert all(row["source"] == "entered" for row in cited)
    assert all(row["source"] is None for row in empty)


def test_catalog_requires_token(client: TestClient) -> None:
    missing = uuid.uuid4()
    paths = [
        "/v1/catalog/crops",
        f"/v1/catalog/crops/{missing}/varieties",
        f"/v1/catalog/crops/{missing}/training-systems",
        f"/v1/catalog/crops/{missing}/stages",
        "/v1/catalog/soil-textures",
    ]
    for path in paths:
        response = client.get(path)
        assert response.status_code == 401
        assert response.json() == {"code": "auth.not_authenticated"}


def test_unknown_crop(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    user = make_user("catalog@agrect.app", "catalog-password")
    headers = auth_header(user)
    missing = uuid.uuid4()
    for path in ("varieties", "training-systems", "stages"):
        response = client.get(f"/v1/catalog/crops/{missing}/{path}", headers=headers)
        assert response.status_code == 404
        assert response.json() == {"code": "catalog.crop_not_found"}
