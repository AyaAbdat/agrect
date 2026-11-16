from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.core.security import hash_password, verify_password
from app.modules.auth.models import AppUser
from app.modules.farms.models import Farm, WeatherSource
from app.modules.farms.service import location_point


def main() -> None:
    settings = get_settings()
    email = settings.demo_user_email
    password = settings.demo_user_password
    lat = settings.demo_farm_lat
    lon = settings.demo_farm_lon
    missing: list[str] = []
    if not email:
        missing.append("DEMO_USER_EMAIL")
    if not password:
        missing.append("DEMO_USER_PASSWORD")
    if lat is None:
        missing.append("DEMO_FARM_LAT")
    if lon is None:
        missing.append("DEMO_FARM_LON")
    if not email or not password or lat is None or lon is None:
        print(f"missing {', '.join(missing)}")
        raise SystemExit(1)

    email_key = email.lower()
    db = SessionLocal()
    try:
        user = db.scalar(select(AppUser).where(AppUser.email == email_key))
        if user is None:
            user = AppUser(email=email_key, password_hash=hash_password(password))
            db.add(user)
            db.flush()
        elif not verify_password(password, user.password_hash):
            user.password_hash = hash_password(password)

        farm = db.scalar(
            select(Farm).where(
                Farm.owner_user_id == user.id,
                Farm.name == settings.demo_farm_name,
            )
        )
        if farm is None:
            farm = Farm(
                owner_user_id=user.id,
                name=settings.demo_farm_name,
                timezone=settings.demo_farm_tz,
                weather_source=WeatherSource.service,
            )
            farm.location = location_point(lon, lat)
            db.add(farm)
        else:
            farm.timezone = settings.demo_farm_tz
            farm.weather_source = WeatherSource.service
            farm.location = location_point(lon, lat)
        db.commit()
        print(
            f"seed ok: user {email_key}, farm {settings.demo_farm_name} "
            f"({lat}, {lon}, {settings.demo_farm_tz})"
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
