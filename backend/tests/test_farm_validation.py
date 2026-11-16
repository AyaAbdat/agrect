from collections.abc import Callable
from decimal import Decimal

from fastapi.testclient import TestClient

from app.modules.auth.models import AppUser
from app.modules.farms.models import Farm


def _owned_farm(
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
) -> tuple[AppUser, Farm]:
    user = make_user("owner@agrect.app", "owner-password")
    farm = make_farm(user, "Farm", Decimal("36"), Decimal("3"))
    return user, farm


def test_station_not_supported(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    user, farm = _owned_farm(make_user, make_farm)
    response = client.put(
        f"/v1/farms/{farm.id}/weather-source",
        headers=auth_header(user),
        json={"weather_source": "station", "lat": "36.0", "lon": "3.0"},
    )
    assert response.status_code == 422
    assert response.json() == {
        "code": "validation_error",
        "fields": {"weather_source": "farm.station_not_supported"},
    }


def test_lat_out_of_range(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    user, farm = _owned_farm(make_user, make_farm)
    response = client.put(
        f"/v1/farms/{farm.id}/weather-source",
        headers=auth_header(user),
        json={"weather_source": "service", "lat": "91", "lon": "3"},
    )
    assert response.status_code == 422
    assert response.json() == {
        "code": "validation_error",
        "fields": {"lat": "farm.lat_out_of_range"},
    }


def test_timezone_invalid(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    user, farm = _owned_farm(make_user, make_farm)
    response = client.put(
        f"/v1/farms/{farm.id}/weather-source",
        headers=auth_header(user),
        json={
            "weather_source": "service",
            "lat": "36",
            "lon": "3",
            "timezone": "Mars/Base",
        },
    )
    assert response.status_code == 422
    assert response.json() == {
        "code": "validation_error",
        "fields": {"timezone": "farm.timezone_invalid"},
    }


def test_valid_update_increments_version(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    user, farm = _owned_farm(make_user, make_farm)
    assert farm.version == 1
    response = client.put(
        f"/v1/farms/{farm.id}/weather-source",
        headers=auth_header(user),
        json={
            "weather_source": "service",
            "lat": "36.123456",
            "lon": "4.654321",
            "timezone": "Africa/Tunis",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["version"] == 2
    assert Decimal(str(body["lat"])) == Decimal("36.123456")
    assert Decimal(str(body["lon"])) == Decimal("4.654321")
    assert body["timezone"] == "Africa/Tunis"
    assert body["weather_source"] == "service"
