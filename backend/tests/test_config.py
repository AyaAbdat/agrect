import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_jwt_secret_shorter_than_32_rejected() -> None:
    with pytest.raises(ValidationError) as exc_info:
        Settings(jwt_secret="0123456789")
    assert "JWT_SECRET must be at least 32 characters" in str(exc_info.value)


def test_jwt_secret_64_characters_accepted() -> None:
    secret = "a" * 64
    settings = Settings(jwt_secret=secret)
    assert settings.jwt_secret == secret
