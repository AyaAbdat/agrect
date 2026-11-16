import uuid

from pydantic import BaseModel


class LoginIn(BaseModel):
    email: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"  # noqa: S105
    expires_in_s: int


class FarmSummary(BaseModel):
    id: uuid.UUID
    name: str


class MeOut(BaseModel):
    id: uuid.UUID
    email: str
    farms: list[FarmSummary]
