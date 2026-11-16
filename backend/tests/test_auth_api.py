from collections.abc import Callable

from fastapi.testclient import TestClient

from app.modules.auth.models import AppUser
from app.modules.farms.models import Farm


def test_login_ok_any_case_email(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
) -> None:
    user = make_user("Demo.User@Agrect.app", "s3cret-pass")
    assert user.email == "demo.user@agrect.app"
    response = client.post(
        "/v1/auth/login",
        json={"email": "DEMO.USER@AGRECT.APP", "password": "s3cret-pass"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in_s"] == 720 * 60
    assert isinstance(body["access_token"], str)
    assert body["access_token"]


def test_login_wrong_password(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
) -> None:
    make_user("a@agrect.app", "right-password")
    response = client.post(
        "/v1/auth/login",
        json={"email": "a@agrect.app", "password": "wrong-password"},
    )
    assert response.status_code == 401
    assert response.json() == {"code": "auth.invalid_credentials"}


def test_login_unknown_email(client: TestClient) -> None:
    response = client.post(
        "/v1/auth/login",
        json={"email": "missing@agrect.app", "password": "whatever"},
    )
    assert response.status_code == 401
    assert response.json() == {"code": "auth.invalid_credentials"}


def test_me_without_token(client: TestClient) -> None:
    response = client.get("/v1/me")
    assert response.status_code == 401
    assert response.json() == {"code": "auth.not_authenticated"}


def test_me_lists_farm(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    user = make_user("owner@agrect.app", "owner-password")
    farm = make_farm(user, "North plot", "36.5", "3.25")
    response = client.get("/v1/me", headers=auth_header(user))
    assert response.status_code == 200
    assert response.json() == {
        "id": str(user.id),
        "email": "owner@agrect.app",
        "farms": [{"id": str(farm.id), "name": "North plot"}],
    }
