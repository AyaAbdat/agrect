import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.security import (
    _make_hasher,
    create_access_token,
    hash_password,
    verify_password,
)


def test_hash_round_trip() -> None:
    password_hash = hash_password("correct-horse")
    assert password_hash != "correct-horse"
    assert verify_password("correct-horse", password_hash)


def test_wrong_password_fails() -> None:
    password_hash = hash_password("correct-horse")
    assert not verify_password("wrong-horse", password_hash)


def test_production_hasher_keeps_argon2_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without TEST_FAST_HASH the hasher is argon2's default cost (tests use a cheap one)."""
    monkeypatch.delenv("TEST_FAST_HASH", raising=False)
    production = _make_hasher()
    default = PasswordHasher()
    assert production.time_cost == default.time_cost
    assert production.memory_cost == default.memory_cost
    assert production.parallelism == default.parallelism
    password_hash = production.hash("correct-horse")
    assert f"m={default.memory_cost},t={default.time_cost},p={default.parallelism}" in password_hash
    assert verify_password("correct-horse", password_hash)
    assert not verify_password("wrong-horse", password_hash)


def test_token_decodes_to_user_id() -> None:
    user_id = uuid.uuid4()
    token = create_access_token(user_id)
    payload = jwt.decode(token, get_settings().jwt_secret, algorithms=["HS256"])
    assert payload["sub"] == str(user_id)
    issued_at = datetime.fromtimestamp(payload["iat"], UTC)
    expires_at = datetime.fromtimestamp(payload["exp"], UTC)
    assert expires_at - issued_at == timedelta(minutes=get_settings().jwt_expire_min)


def test_expired_token_rejected(client: TestClient) -> None:
    token = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "iat": datetime.now(UTC) - timedelta(hours=2),
            "exp": datetime.now(UTC) - timedelta(seconds=30),
        },
        get_settings().jwt_secret,
        algorithm="HS256",
    )
    response = client.get("/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.json() == {"code": "auth.not_authenticated"}
    assert token not in response.text
