import uuid
from collections.abc import Callable
from decimal import Decimal

from fastapi.testclient import TestClient

from app.modules.auth.models import AppUser
from app.modules.farms.models import Farm


def test_owner_reads_own_farm(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    user = make_user("a@agrect.app", "password-a")
    farm = make_farm(user, "Farm A", Decimal("36.1"), Decimal("2.2"))
    response = client.get(f"/v1/farms/{farm.id}", headers=auth_header(user))
    assert response.status_code == 200
    body = response.json()
    assert Decimal(str(body["lat"])) == Decimal("36.1")
    assert Decimal(str(body["lon"])) == Decimal("2.2")
    assert body["name"] == "Farm A"


def test_other_users_farm_is_not_found(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    user_a = make_user("a@agrect.app", "password-a")
    user_b = make_user("b@agrect.app", "password-b")
    farm_b = make_farm(user_b, "Farm B", Decimal("1.5"), Decimal("10.5"))
    response = client.get(f"/v1/farms/{farm_b.id}", headers=auth_header(user_a))
    assert response.status_code == 404
    assert response.json() == {"code": "farm.not_found"}


def test_unknown_farm_is_not_found(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    user = make_user("a@agrect.app", "password-a")
    response = client.get(f"/v1/farms/{uuid.uuid4()}", headers=auth_header(user))
    assert response.status_code == 404
    assert response.json() == {"code": "farm.not_found"}


def test_put_other_users_farm_is_not_found(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    user_a = make_user("a@agrect.app", "password-a")
    user_b = make_user("b@agrect.app", "password-b")
    farm_a = make_farm(user_a, "Farm A", Decimal("36.1"), Decimal("2.2"))
    response = client.put(
        f"/v1/farms/{farm_a.id}/weather-source",
        headers=auth_header(user_b),
        json={"weather_source": "service", "lat": "36.2", "lon": "2.3"},
    )
    assert response.status_code == 404
    assert response.json() == {"code": "farm.not_found"}
