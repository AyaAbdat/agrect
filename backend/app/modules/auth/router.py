from fastapi import APIRouter
from sqlalchemy import select

from app.core.config import get_settings
from app.core.deps import CurrentUser, Db
from app.core.errors import AppError
from app.core.security import create_access_token, verify_password
from app.modules.auth.models import AppUser
from app.modules.auth.schemas import FarmSummary, LoginIn, MeOut, TokenOut
from app.modules.farms.models import Farm

router = APIRouter(tags=["auth"])

# Not a credential. verify_password still runs when the email is unknown.
_UNKNOWN_EMAIL_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=4$wyvE2bUpKu8KLOS0nqgZ0g$"
    "1qmb4DQS7zpBat2uPlAC2ww+HekleEm+m3edeiStYjc"
)


@router.post("/auth/login", response_model=TokenOut)
def login(body: LoginIn, db: Db) -> TokenOut:
    user = db.scalar(select(AppUser).where(AppUser.email == body.email.lower()))
    password_hash = _UNKNOWN_EMAIL_HASH if user is None else user.password_hash
    if not verify_password(body.password, password_hash) or user is None:
        raise AppError("auth.invalid_credentials", 401)
    settings = get_settings()
    return TokenOut(
        access_token=create_access_token(user.id),
        expires_in_s=settings.jwt_expire_min * 60,
    )


@router.get("/me", response_model=MeOut)
def me(user: CurrentUser, db: Db) -> MeOut:
    farms = db.scalars(
        select(Farm).where(Farm.owner_user_id == user.id).order_by(Farm.name, Farm.id)
    ).all()
    return MeOut(
        id=user.id,
        email=user.email,
        farms=[FarmSummary(id=farm.id, name=farm.name) for farm in farms],
    )
