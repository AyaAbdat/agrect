import math
from collections.abc import Callable
from decimal import Decimal

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.modules.auth.models import AppUser
from app.modules.farms.models import Farm


def rectangle(lat: float, lon: float, width_m: float, height_m: float) -> dict:
    """Rectangle of width_m by height_m metres around a centre (lat, lon).

    dlat = m / 111320
    dlon = m / (111320 * cos(lat))
    """
    dlat = (height_m / 2) / 111320
    dlon = (width_m / 2) / (111320 * math.cos(math.radians(lat)))
    west = lon - dlon
    east = lon + dlon
    south = lat - dlat
    north = lat + dlat
    return {
        "type": "Polygon",
        "coordinates": [
            [
                [west, south],
                [east, south],
                [east, north],
                [west, north],
                [west, south],
            ]
        ],
    }


def line_toward(lat: float, lon: float, azimuth_deg: float, length_m: float = 40.0) -> dict:
    rad = math.radians(azimuth_deg)
    dlat = (length_m * math.cos(rad)) / 111320
    dlon = (length_m * math.sin(rad)) / (111320 * math.cos(math.radians(lat)))
    return {
        "type": "LineString",
        "coordinates": [[lon, lat], [lon + dlon, lat + dlat]],
    }


def _demo_center() -> tuple[float, float]:
    settings = get_settings()
    if settings.demo_farm_lat is None or settings.demo_farm_lon is None:
        raise AssertionError("DEMO_FARM_LAT and DEMO_FARM_LON must be set")
    return float(settings.demo_farm_lat), float(settings.demo_farm_lon)


def _farm(
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> tuple[Farm, dict[str, str], float, float]:
    settings = get_settings()
    if settings.demo_farm_lat is None or settings.demo_farm_lon is None:
        raise AssertionError("DEMO_FARM_LAT and DEMO_FARM_LON must be set")
    user = make_user("blocks@agrect.app", "blocks-password")
    farm = make_farm(user, "Demo", settings.demo_farm_lat, settings.demo_farm_lon)
    lat, lon = _demo_center()
    return farm, auth_header(user), lat, lon


def _places(value: str) -> int:
    return len(value.split(".", 1)[1])


def test_hundred_metre_square_area(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm, headers, lat, lon = _farm(make_user, make_farm, auth_header)
    response = client.post(
        f"/v1/farms/{farm.id}/blocks",
        headers=headers,
        json={
            "name": "Square",
            "outline": rectangle(lat, lon, 100, 100),
            "net_area_ha": "0.5",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert isinstance(body["gross_area_ha"], str)
    assert _places(body["gross_area_ha"]) == 4
    area = Decimal(body["gross_area_ha"])
    assert abs(area - Decimal("1")) <= Decimal("0.005")
    assert body["net_area_ha"] == "0.5000"
    assert body["row_bearing_deg"] is None
    assert body["outline"]["type"] == "Polygon"
    assert body["sources"]["gross_area_ha"] == "calculated"
    assert response.headers["etag"] == str(body["version"])
    read = client.get(f"/v1/blocks/{body['id']}", headers=headers)
    assert read.status_code == 200
    assert read.json()["gross_area_ha"] == body["gross_area_ha"]
    listed = client.get(f"/v1/farms/{farm.id}/blocks", headers=headers)
    assert listed.json()[0]["outline"]["type"] == "Polygon"
    assert read.headers["etag"] == str(body["version"])
    renamed = client.patch(
        f"/v1/blocks/{body['id']}",
        headers={**headers, "If-Match": str(body["version"])},
        json={"name": "Square renamed"},
    )
    assert renamed.status_code == 200
    history = client.get(f"/v1/blocks/{body['id']}/history", headers=headers)
    assert history.json()[0]["changed_fields"] == ["name"]


def test_row_bearing_is_undirected(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm, headers, lat, lon = _farm(make_user, make_farm, auth_header)
    outline = rectangle(lat, lon, 100, 100)
    cases = (
        ("North", 0, Decimal("0.0")),
        ("East", 90, Decimal("90.0")),
        ("West", 270, Decimal("90.0")),
        ("Southwest", 225, Decimal("45.0")),
    )
    for name, azimuth, expected in cases:
        response = client.post(
            f"/v1/farms/{farm.id}/blocks",
            headers=headers,
            json={
                "name": name,
                "outline": outline,
                "row_line": line_toward(lat, lon, azimuth),
            },
        )
        assert response.status_code == 201, response.json()
        bearing_text = response.json()["row_bearing_deg"]
        assert isinstance(bearing_text, str)
        assert _places(bearing_text) == 1
        assert abs(Decimal(bearing_text) - expected) <= Decimal("0.5")
        assert response.json()["sources"]["row_bearing_deg"] == "calculated"


def test_bowtie_outline_rejected(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm, headers, lat, lon = _farm(make_user, make_farm, auth_header)
    bowtie = {
        "type": "Polygon",
        "coordinates": [
            [
                [lon, lat],
                [lon + 0.001, lat + 0.001],
                [lon + 0.001, lat],
                [lon, lat + 0.001],
                [lon, lat],
            ]
        ],
    }
    response = client.post(
        f"/v1/farms/{farm.id}/blocks",
        headers=headers,
        json={"name": "Bowtie", "outline": bowtie},
    )
    assert response.status_code == 422
    assert response.json() == {
        "code": "validation_error",
        "fields": {"outline": "block.outline_invalid"},
    }
    listed = client.get(f"/v1/farms/{farm.id}/blocks", headers=headers)
    assert listed.json() == []


def test_row_line_outside_and_invalid(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm, headers, lat, lon = _farm(make_user, make_farm, auth_header)
    outline = rectangle(lat, lon, 100, 100)
    outside = client.post(
        f"/v1/farms/{farm.id}/blocks",
        headers=headers,
        json={
            "name": "Outside",
            "outline": outline,
            "row_line": {
                "type": "LineString",
                "coordinates": [[lon + 1, lat + 1], [lon + 1.1, lat + 1.1]],
            },
        },
    )
    assert outside.status_code == 422
    assert outside.json() == {
        "code": "validation_error",
        "fields": {"row_line": "block.row_line_outside"},
    }
    point = client.post(
        f"/v1/farms/{farm.id}/blocks",
        headers=headers,
        json={
            "name": "Point",
            "row_line": {"type": "Point", "coordinates": [lon, lat]},
        },
    )
    assert point.status_code == 422
    assert point.json()["fields"]["row_line"] == "block.row_line_invalid"
    repeated = client.post(
        f"/v1/farms/{farm.id}/blocks",
        headers=headers,
        json={
            "name": "Repeated",
            "row_line": {"type": "LineString", "coordinates": [[lon, lat], [lon, lat]]},
        },
    )
    assert repeated.status_code == 422
    assert repeated.json()["fields"]["row_line"] == "block.row_line_invalid"


def test_net_area_rules(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm, headers, lat, lon = _farm(make_user, make_farm, auth_header)
    zero = client.post(
        f"/v1/farms/{farm.id}/blocks",
        headers=headers,
        json={"name": "Zero", "net_area_ha": "0"},
    )
    assert zero.status_code == 422
    assert zero.json() == {
        "code": "validation_error",
        "fields": {"net_area_ha": "block.net_area_must_be_positive"},
    }
    exceeds = client.post(
        f"/v1/farms/{farm.id}/blocks",
        headers=headers,
        json={
            "name": "Too big",
            "outline": rectangle(lat, lon, 100, 100),
            "net_area_ha": "1.2",
        },
    )
    assert exceeds.status_code == 422
    assert exceeds.json() == {
        "code": "validation_error",
        "fields": {"net_area_ha": "block.net_area_exceeds_gross"},
    }
    listed = client.get(f"/v1/farms/{farm.id}/blocks", headers=headers)
    assert listed.json() == []
