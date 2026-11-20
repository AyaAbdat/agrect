"""Block GDD overrides win over the crop setting."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.auth.models import AppUser
from app.modules.catalog.loader import load_catalog
from app.modules.farms.models import Farm
from tests.test_weather_api import _Feed, _local, _point

_ZONE = ZoneInfo("Africa/Algiers")


def _today(farm: Farm):
    return datetime.now(UTC).astimezone(ZoneInfo(farm.timezone)).date()


def _crop_id(client: TestClient, headers: dict[str, str], code: str) -> str:
    crops = client.get("/v1/catalog/crops", headers=headers)
    assert crops.status_code == 200
    return str(next(row["id"] for row in crops.json() if row["code"] == code))


def _first_stage(client: TestClient, headers: dict[str, str], crop_id: str) -> str:
    response = client.get(f"/v1/catalog/crops/{crop_id}/stages", headers=headers)
    assert response.status_code == 200
    return str(response.json()["stages"][0]["id"])


def _stage(payload: dict[str, object], stage_id: str) -> dict[str, object]:
    stages = payload["stages"]
    assert isinstance(stages, list)
    return next(row for row in stages if row["stage"]["id"] == stage_id)


def test_block_override_changes_total_and_predictions(
    client: TestClient,
    db: Session,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
    monkeypatch,
) -> None:
    load_catalog()
    user = make_user("gdd-block@agrect.app", "password-weather")
    farm = make_farm(user, "GDD blocks", Decimal("36.5"), Decimal("3.2"))
    farm.timezone = "Africa/Algiers"
    db.commit()
    headers = auth_header(user)
    apple_id = _crop_id(client, headers, "apple")
    stage_id = _first_stage(client, headers, apple_id)
    day = _today(farm) - timedelta(days=3)
    feed = _Feed(
        [
            _point(_local(day, 8), Decimal("14")),
            _point(_local(day, 15), Decimal("30")),
        ]
    )
    monkeypatch.setattr("app.modules.weather.service.fetch_forecast", feed)
    assert client.post(f"/v1/farms/{farm.id}/weather/refresh", headers=headers).status_code == 200

    north = client.post(
        f"/v1/farms/{farm.id}/blocks",
        headers=headers,
        json={"name": "North", "crop_id": apple_id},
    )
    south = client.post(
        f"/v1/farms/{farm.id}/blocks",
        headers=headers,
        json={"name": "South", "crop_id": apple_id},
    )
    assert north.status_code == 201
    assert south.status_code == 201
    block_a = str(north.json()["id"])
    block_b = str(south.json()["id"])

    empty = client.get(f"/v1/blocks/{block_a}/gdd-setting", headers=headers)
    assert empty.status_code == 200
    assert empty.json()["method"] is None
    assert empty.json()["version"] is None

    out_of_range = client.put(
        f"/v1/blocks/{block_a}/gdd-setting",
        headers=headers,
        json={"base_c": "21", "method": "average"},
    )
    assert out_of_range.status_code == 422
    assert out_of_range.json()["fields"]["base_c"] == "gdd.base_out_of_range"
    not_above = client.put(
        f"/v1/blocks/{block_a}/gdd-setting",
        headers=headers,
        json={"base_c": "10", "upper_c": "10", "method": "average"},
    )
    assert not_above.status_code == 422
    assert not_above.json()["fields"]["upper_c"] == "gdd.upper_not_above_base"

    crop = client.put(
        f"/v1/farms/{farm.id}/gdd-settings/{apple_id}",
        headers=headers,
        json={"base_c": "10", "method": "average", "start_date": day.isoformat()},
    )
    assert crop.status_code == 200
    entered = client.put(
        f"/v1/farms/{farm.id}/stage-dd",
        headers=headers,
        json={
            "crop_id": apple_id,
            "items": [
                {
                    "stage_def_id": stage_id,
                    "dd_value": "30",
                    "base_c": "10",
                    "method": "average",
                }
            ],
        },
    )
    assert entered.status_code == 200
    for block_id in (block_a, block_b):
        started = client.put(
            f"/v1/blocks/{block_id}/seasons/{day.year}",
            headers=headers,
            json={"start_date": day.isoformat()},
        )
        assert started.status_code == 200

    def degree_days(block_id: str) -> dict[str, object]:
        response = client.get(
            f"/v1/farms/{farm.id}/weather/degree-days",
            headers=headers,
            params={"crop_id": apple_id, "block_id": block_id, "from": day.isoformat()},
        )
        assert response.status_code == 200
        body = response.json()
        assert isinstance(body, dict)
        return body

    def stages(block_id: str) -> dict[str, object]:
        response = client.get(
            f"/v1/blocks/{block_id}/stages",
            headers=headers,
            params={"year": day.year},
        )
        assert response.status_code == 200
        body = response.json()
        assert isinstance(body, dict)
        return body

    before = degree_days(block_a)
    assert Decimal(str(before["gdd_total"])) == Decimal("12")
    assert before["setting"]["override"] is False
    assert before["setting"]["base_c"] == "10"
    before_stage = _stage(stages(block_a), stage_id)
    assert Decimal(str(before_stage["dd_needed"])) == Decimal("30")
    assert before_stage["reason"] is None
    other_before = _stage(stages(block_b), stage_id)
    assert other_before["reason"] is None

    saved = client.put(
        f"/v1/blocks/{block_a}/gdd-setting",
        headers=headers,
        json={"base_c": "0", "method": "average", "start_date": day.isoformat()},
    )
    assert saved.status_code == 200
    assert saved.json()["base_c"] == "0"
    assert saved.json()["method"] == "average"
    assert saved.json()["version"] == 1

    overridden = degree_days(block_a)
    assert Decimal(str(overridden["gdd_total"])) == Decimal("22")
    assert overridden["setting"]["override"] is True
    assert overridden["setting"]["base_c"] == "0"
    untouched = degree_days(block_b)
    assert Decimal(str(untouched["gdd_total"])) == Decimal("12")
    assert untouched["setting"]["override"] is False

    moved = _stage(stages(block_a), stage_id)
    assert moved["reason"] == "phenology.setting_mismatch"
    assert moved["date"] is None
    assert moved["dd_needed"] is None
    assert stages(block_a)["setting"]["base_c"] == "0"
    still = _stage(stages(block_b), stage_id)
    assert still["reason"] is None
    assert Decimal(str(still["dd_needed"])) == Decimal("30")

    removed = client.delete(f"/v1/blocks/{block_a}/gdd-setting", headers=headers)
    assert removed.status_code == 204
    cleared = client.get(f"/v1/blocks/{block_a}/gdd-setting", headers=headers)
    assert cleared.status_code == 200
    assert cleared.json()["method"] is None
    restored = degree_days(block_a)
    assert Decimal(str(restored["gdd_total"])) == Decimal("12")
    assert restored["setting"]["override"] is False
    assert restored["setting"]["base_c"] == "10"
    back = _stage(stages(block_a), stage_id)
    assert back["reason"] is None
    assert Decimal(str(back["dd_needed"])) == Decimal("30")

    other_user = make_user("gdd-other@agrect.app", "password-weather")
    other_farm = make_farm(other_user, "Other farm", Decimal("36.6"), Decimal("3.3"))
    other_headers = auth_header(other_user)
    foreign = client.post(
        f"/v1/farms/{other_farm.id}/blocks",
        headers=other_headers,
        json={"name": "Foreign", "crop_id": apple_id},
    )
    assert foreign.status_code == 201
    foreign_id = str(foreign.json()["id"])
    for response in (
        client.get(f"/v1/blocks/{foreign_id}/gdd-setting", headers=headers),
        client.put(
            f"/v1/blocks/{foreign_id}/gdd-setting",
            headers=headers,
            json={"base_c": "10", "method": "average"},
        ),
        client.delete(f"/v1/blocks/{foreign_id}/gdd-setting", headers=headers),
    ):
        assert response.status_code == 404
        assert response.json() == {"code": "block.not_found"}
    cross = client.get(
        f"/v1/farms/{farm.id}/weather/degree-days",
        headers=headers,
        params={"crop_id": apple_id, "block_id": foreign_id, "from": day.isoformat()},
    )
    assert cross.status_code == 404
    assert cross.json() == {"code": "block.not_found"}
