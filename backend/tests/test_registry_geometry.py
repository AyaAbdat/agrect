import math
from collections.abc import Callable
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.auth.models import AppUser
from app.modules.registry.models import Block


def rectangle(lat: float, lon: float, width_m: float, height_m: float) -> dict:
    """Rectangle of width_m by height_m metres around a centre (lat, lon)."""
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


def _places(value: str) -> int:
    return len(value.split(".", 1)[1])


def test_geometry_preview_square_north_and_bowtie(
    client: TestClient,
    db: Session,
    make_user: Callable[[str, str], AppUser],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    user = make_user("geometry@agrect.app", "geometry-password")
    headers = auth_header(user)
    lat, lon = 36.0, 3.0
    square = client.post(
        "/v1/calc/registry/geometry",
        headers=headers,
        json={"outline": rectangle(lat, lon, 100, 100)},
    )
    assert square.status_code == 200, square.json()
    body = square.json()
    assert isinstance(body["gross_area_ha"], str)
    assert _places(body["gross_area_ha"]) == 4
    assert abs(Decimal(body["gross_area_ha"]) - Decimal("1")) <= Decimal("0.005")
    assert body["row_bearing_deg"] is None
    assert body["source"] == "calculated"

    north = client.post(
        "/v1/calc/registry/geometry",
        headers=headers,
        json={"row_line": line_toward(lat, lon, 0)},
    )
    assert north.status_code == 200, north.json()
    north_body = north.json()
    assert north_body["gross_area_ha"] is None
    assert north_body["row_bearing_deg"] == "0.0"
    assert north_body["source"] == "calculated"

    bowtie = client.post(
        "/v1/calc/registry/geometry",
        headers=headers,
        json={
            "outline": {
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
        },
    )
    assert bowtie.status_code == 422
    assert bowtie.json() == {
        "code": "validation_error",
        "fields": {"outline": "block.outline_invalid"},
    }
    outside = client.post(
        "/v1/calc/registry/geometry",
        headers=headers,
        json={
            "outline": rectangle(lat, lon, 100, 100),
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
    assert db.scalar(select(func.count()).select_from(Block)) == 0
