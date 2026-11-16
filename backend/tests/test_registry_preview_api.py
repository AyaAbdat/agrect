from collections.abc import Callable

from fastapi.testclient import TestClient

from app.modules.auth.models import AppUser


def _headers(
    make_user: Callable[[str, str], AppUser],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> dict[str, str]:
    user = make_user("registry@agrect.app", "registry-password")
    return auth_header(user)


def test_irrigation_drip_vector(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    response = client.post(
        "/v1/calc/registry/irrigation",
        headers=_headers(make_user, auth_header),
        json={
            "entry_mode": "layout",
            "row_spacing_m": "4.00",
            "laterals_per_row": 2,
            "emitter_spacing_m": "0.75",
            "emitter_flow_lph": "4.0",
            "net_area_ha": "1",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["q_ha_m3h"] == "26.67"
    assert body["q_block_m3h"] == "26.67"
    assert body["rate_mm_h"] == "2.67"
    assert body["row_m_per_ha"] == "2500"
    assert body["lateral_m_per_ha"] == "5000"
    assert body["emitters_per_ha"] == "6667"
    assert body["valves"] == []
    assert body["source"] == "calculated"


def test_missing_emitter_flow_leaves_q_null(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    response = client.post(
        "/v1/calc/registry/irrigation",
        headers=_headers(make_user, auth_header),
        json={
            "entry_mode": "layout",
            "row_spacing_m": "4.00",
            "laterals_per_row": 2,
            "emitter_spacing_m": "0.75",
            "net_area_ha": "1",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["q_ha_m3h"] is None
    assert body["q_block_m3h"] is None
    assert body["rate_mm_h"] is None
    assert body["row_m_per_ha"] == "2500"
    assert body["lateral_m_per_ha"] == "5000"
    assert body["emitters_per_ha"] == "6667"
    assert body["source"] == "calculated"


def test_negative_row_spacing(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    response = client.post(
        "/v1/calc/registry/irrigation",
        headers=_headers(make_user, auth_header),
        json={
            "entry_mode": "layout",
            "row_spacing_m": "-4.00",
            "laterals_per_row": 2,
            "emitter_spacing_m": "0.75",
            "emitter_flow_lph": "4.0",
            "net_area_ha": "1",
        },
    )
    assert response.status_code == 422
    assert response.json() == {
        "code": "validation_error",
        "fields": {"row_spacing_m": "registry.row_spacing_m_must_be_positive"},
    }


def test_layout_lengths_stop_when_an_input_is_missing(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    response = client.post(
        "/v1/calc/registry/irrigation",
        headers=_headers(make_user, auth_header),
        json={"entry_mode": "layout", "row_spacing_m": "4"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["row_m_per_ha"] == "2500"
    assert body["lateral_m_per_ha"] is None
    assert body["emitters_per_ha"] is None
    assert body["q_ha_m3h"] is None


def test_preview_requires_token(client: TestClient) -> None:
    planting = client.post("/v1/calc/registry/planting", json={"mode": "spacing"})
    irrigation = client.post("/v1/calc/registry/irrigation", json={"entry_mode": "layout"})
    geometry = client.post("/v1/calc/registry/geometry", json={})
    assert planting.status_code == 401
    assert irrigation.status_code == 401
    assert geometry.status_code == 401
    assert planting.json()["code"] == "auth.not_authenticated"
    assert irrigation.json()["code"] == "auth.not_authenticated"
    assert geometry.json()["code"] == "auth.not_authenticated"


def test_planting_spacing_vector(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    response = client.post(
        "/v1/calc/registry/planting",
        headers=_headers(make_user, auth_header),
        json={
            "mode": "spacing",
            "row_spacing_m": "3.00",
            "tree_spacing_m": "1.50",
            "net_area_ha": "1",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["trees_per_ha"] == 2222
    assert body["tree_spacing_m"] == "1.50"
    assert body["trees_in_block"] == 2222
    assert body["source"] == "calculated"


def test_planting_missing_optional_is_null(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    response = client.post(
        "/v1/calc/registry/planting",
        headers=_headers(make_user, auth_header),
        json={"mode": "spacing", "row_spacing_m": "3.00"},
    )
    assert response.status_code == 200
    assert response.json() == {
        "trees_per_ha": None,
        "tree_spacing_m": None,
        "trees_in_block": None,
        "source": "calculated",
    }


def test_valve_split_display_rounding(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    response = client.post(
        "/v1/calc/registry/irrigation",
        headers=_headers(make_user, auth_header),
        json={
            "entry_mode": "typed_flow",
            "typed_flow_basis": "block",
            "typed_flow_m3h": "120",
            "net_area_ha": "3",
            "rows_total": 120,
            "valves": [
                {"row_from": 1, "row_to": 40},
                {"row_from": 41, "row_to": 80},
                {"row_from": 81, "row_to": 120},
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["q_ha_m3h"] == "40.00"
    assert body["q_block_m3h"] == "120.00"
    assert body["rate_mm_h"] == "4.00"
    assert body["row_m_per_ha"] is None
    assert body["lateral_m_per_ha"] is None
    assert body["emitters_per_ha"] is None
    assert body["valves"] == [
        {"row_from": 1, "row_to": 40, "rows": 40, "area_ha": "1.0000", "q_m3h": "40.00"},
        {"row_from": 41, "row_to": 80, "rows": 40, "area_ha": "1.0000", "q_m3h": "40.00"},
        {"row_from": 81, "row_to": 120, "rows": 40, "area_ha": "1.0000", "q_m3h": "40.00"},
    ]
    assert body["source"] == "calculated"


def test_typed_block_flow_per_hectare(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    response = client.post(
        "/v1/calc/registry/irrigation",
        headers=_headers(make_user, auth_header),
        json={
            "entry_mode": "typed_flow",
            "typed_flow_basis": "block",
            "typed_flow_m3h": "40",
            "net_area_ha": "1.50",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["q_ha_m3h"] == "26.67"
    assert body["q_block_m3h"] == "40.00"
    assert body["rate_mm_h"] == "2.67"
    assert body["source"] == "calculated"
