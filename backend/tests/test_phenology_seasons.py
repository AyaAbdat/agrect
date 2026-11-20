import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.events import subscribe, unsubscribe
from app.modules.auth.models import AppUser
from app.modules.catalog.loader import load_catalog
from app.modules.farms.models import Farm
from app.modules.phenology.calc import predict
from app.modules.weather.models import WeatherDaily

_ZONE = ZoneInfo("Africa/Algiers")


def _today(farm: Farm):
    return datetime.now(UTC).astimezone(ZoneInfo(farm.timezone)).date()


def _crop_id(client: TestClient, headers: dict[str, str], code: str) -> str:
    crops = client.get("/v1/catalog/crops", headers=headers)
    assert crops.status_code == 200
    return str(next(row["id"] for row in crops.json() if row["code"] == code))


def _stages(client: TestClient, headers: dict[str, str], crop_id: str) -> list[dict[str, object]]:
    response = client.get(f"/v1/catalog/crops/{crop_id}/stages", headers=headers)
    assert response.status_code == 200
    stages = response.json()["stages"]
    assert isinstance(stages, list)
    return stages


def _weather(db: Session, farm: Farm, start, days: int) -> None:
    today = _today(farm)
    for offset in range(days):
        day = start + timedelta(days=offset)
        db.add(
            WeatherDaily(
                farm_id=farm.id,
                date=day,
                tmin_c=Decimal("20"),
                tmax_c=Decimal("20"),
                hours_count=24,
                is_forecast=day >= today,
                source="estimated",
                inputs_hash="f" * 64,
            )
        )
    db.commit()


def _enter(
    client: TestClient,
    farm: Farm,
    headers: dict[str, str],
    crop_id: str,
    items: list[dict[str, str]],
) -> None:
    saved = client.put(
        f"/v1/farms/{farm.id}/stage-dd",
        headers=headers,
        json={"crop_id": crop_id, "items": items},
    )
    assert saved.status_code == 200


def test_predictions_follow_calc_and_move_with_observations(
    client: TestClient,
    db: Session,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    load_catalog()
    user = make_user("seasons@agrect.app", "seasons-password")
    farm = make_farm(user, "Seasons", Decimal("36.7"), Decimal("3.1"))
    farm.timezone = "Africa/Algiers"
    db.commit()
    headers = auth_header(user)
    apple_id = _crop_id(client, headers, "apple")
    stages = _stages(client, headers, apple_id)
    chosen = stages[:3]
    created = client.post(
        f"/v1/farms/{farm.id}/blocks",
        headers=headers,
        json={"name": "North", "crop_id": apple_id},
    )
    assert created.status_code == 201
    block_id = created.json()["id"]
    spare = client.post(
        f"/v1/farms/{farm.id}/blocks",
        headers=headers,
        json={"name": "South", "crop_id": apple_id},
    )
    assert spare.status_code == 201
    setting = client.put(
        f"/v1/farms/{farm.id}/gdd-settings/{apple_id}",
        headers=headers,
        json={"base_c": "10", "upper_c": None, "method": "average", "start_date": None},
    )
    assert setting.status_code == 200
    _enter(
        client,
        farm,
        headers,
        apple_id,
        [
            {
                "stage_def_id": str(stage["id"]),
                "dd_value": value,
                "base_c": "10",
                "method": "average",
            }
            for stage, value in zip(chosen, ("30", "50", "80"), strict=True)
        ],
    )
    today = _today(farm)
    start = today - timedelta(days=2)
    _weather(db, farm, start, 20)
    year = today.year
    missing = client.get(f"/v1/blocks/{block_id}/seasons/{year}", headers=headers)
    assert missing.status_code == 404
    both = client.put(
        f"/v1/blocks/{block_id}/seasons/{year}",
        headers=headers,
        json={"start_date": start.isoformat(), "start_stage_def_id": chosen[0]["id"]},
    )
    assert both.status_code == 422
    assert both.json()["fields"]["start_date"] == "phenology.season_start_required"

    published: list[str] = []

    def hear(payload: dict[str, object]) -> None:
        stage_id = payload.get("stage_def_id")
        if isinstance(stage_id, uuid.UUID):
            published.append(str(stage_id))

    subscribe("stage.predicted", hear)
    try:
        saved = client.put(
            f"/v1/blocks/{block_id}/seasons/{year}",
            headers=headers,
            json={"start_date": start.isoformat()},
        )
        assert saved.status_code == 200
        season_id = saved.json()["id"]
        assert saved.json()["start_observed"] is False
        assert saved.json()["status"] == "open"
        again = client.put(
            f"/v1/blocks/{block_id}/seasons/{year}",
            headers=headers,
            json={"start_date": start.isoformat()},
        )
        assert again.status_code == 200
        assert len(published) == 3

        specs = [
            (uuid.UUID(str(stage["id"])), index + 1, Decimal(value))
            for index, (stage, value) in enumerate(zip(chosen, ("30", "50", "80"), strict=True))
        ]
        series = [
            (
                start + timedelta(days=offset),
                Decimal("10"),
                "forecast" if start + timedelta(days=offset) >= today else "observed_weather",
            )
            for offset in range(20)
        ]
        expected = predict(start, series, specs, {}, today=today)
        assert [row.date for row in expected] == [
            start + timedelta(days=2),
            start + timedelta(days=4),
            start + timedelta(days=7),
        ]
        body = client.get(
            f"/v1/blocks/{block_id}/stages",
            headers=headers,
            params={"year": year},
        )
        assert body.status_code == 200
        payload = body.json()
        assert payload["history_status"] == "empty"
        assert payload["setting"] == {"base_c": "10", "upper_c": None, "method": "average"}
        assert payload["today"]["dd_counted"] == "30"
        assert payload["today"]["current_stage"]["code"] == chosen[0]["code"]
        assert payload["today"]["next_stage"]["code"] == chosen[1]["code"]
        by_code = {row["stage"]["code"]: row for row in payload["stages"]}
        for stage, call in zip(chosen, expected, strict=True):
            row = by_code[str(stage["code"])]
            assert row["label"] == "predicted"
            assert row["date"] == call.date.isoformat()
            assert row["dd_needed"] == format(call.dd_needed, "f")
            assert row["dd_counted"] == format(call.dd_counted, "f")
            assert row["dd_source"] == "entered"
            assert row["citation"] is None
            assert row["reason"] is None
            assert row["earliest"] is None
            assert row["latest"] is None
        assert by_code[str(stages[3]["code"])]["label"] == "not_enough_data"
        assert by_code[str(stages[3]["code"])]["dd_needed"] is None
        assert len(published) == 3

        summary = client.get(
            f"/v1/farms/{farm.id}/stages/summary",
            headers=headers,
            params={"crop_id": apple_id},
        )
        assert summary.status_code == 200
        blocks = {row["block_id"]: row for row in summary.json()["blocks"]}
        assert blocks[block_id]["current_stage"]["code"] == chosen[0]["code"]
        assert blocks[block_id]["next_stage"]["stage"]["code"] == chosen[1]["code"]
        assert blocks[block_id]["next_stage"]["date"] == expected[1].date.isoformat()
        assert blocks[spare.json()["id"]]["current_stage"] is None
        assert blocks[spare.json()["id"]]["next_stage"] is None

        future = client.post(
            f"/v1/block-seasons/{season_id}/observations",
            headers=headers,
            json={
                "stage_def_id": chosen[0]["id"],
                "observed_on": (today + timedelta(days=1)).isoformat(),
            },
        )
        assert future.status_code == 422
        assert future.json()["fields"]["observed_on"] == "phenology.observed_in_future"
        early = client.post(
            f"/v1/block-seasons/{season_id}/observations",
            headers=headers,
            json={
                "stage_def_id": chosen[1]["id"],
                "observed_on": (start - timedelta(days=1)).isoformat(),
            },
        )
        assert early.status_code == 422
        assert early.json()["fields"]["observed_on"] == "phenology.before_season_start"

        observed = client.post(
            f"/v1/block-seasons/{season_id}/observations",
            headers=headers,
            json={
                "stage_def_id": chosen[0]["id"],
                "observed_on": start.isoformat(),
                "share_pct": "40",
            },
        )
        assert observed.status_code == 201
        obs_id = observed.json()["id"]
        moved = predict(start, series, specs, {uuid.UUID(str(chosen[0]["id"])): start}, today=today)
        after = client.get(
            f"/v1/blocks/{block_id}/stages",
            headers=headers,
            params={"year": year},
        )
        assert after.status_code == 200
        moved_rows = {row["stage"]["code"]: row for row in after.json()["stages"]}
        assert moved_rows[str(chosen[0]["code"])]["label"] == "observed"
        assert moved_rows[str(chosen[0]["code"])]["date"] == start.isoformat()
        assert moved_rows[str(chosen[1]["code"])]["date"] == moved[1].date.isoformat()
        assert moved_rows[str(chosen[2]["code"])]["date"] == moved[2].date.isoformat()
        assert moved[1].date == start + timedelta(days=2)
        assert moved[2].date == start + timedelta(days=5)
        assert after.json()["today"]["current_stage"]["code"] == chosen[1]["code"]
        assert after.json()["today"]["next_stage"]["code"] == chosen[2]["code"]
        assert len(published) == 6

        removed = client.delete(
            f"/v1/block-seasons/{season_id}/observations/{obs_id}",
            headers=headers,
        )
        assert removed.status_code == 204
        restored = client.get(
            f"/v1/blocks/{block_id}/stages",
            headers=headers,
            params={"year": year},
        )
        assert restored.status_code == 200
        restored_rows = {row["stage"]["code"]: row for row in restored.json()["stages"]}
        for stage, call in zip(chosen, expected, strict=True):
            assert restored_rows[str(stage["code"])]["label"] == "predicted"
            assert restored_rows[str(stage["code"])]["date"] == call.date.isoformat()
        assert len(published) == 9
    finally:
        unsubscribe("stage.predicted", hear)


def test_no_gdd_setting_blocks_every_stage(
    client: TestClient,
    db: Session,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    load_catalog()
    user = make_user("nosetting@agrect.app", "seasons-password")
    farm = make_farm(user, "No setting", Decimal("36.7"), Decimal("3.1"))
    headers = auth_header(user)
    apple_id = _crop_id(client, headers, "apple")
    stage_id = _stages(client, headers, apple_id)[0]["id"]
    created = client.post(
        f"/v1/farms/{farm.id}/blocks",
        headers=headers,
        json={"name": "North", "crop_id": apple_id},
    )
    block_id = created.json()["id"]
    _enter(
        client,
        farm,
        headers,
        apple_id,
        [{"stage_def_id": str(stage_id), "dd_value": "30", "base_c": "10", "method": "average"}],
    )
    today = _today(farm)
    start = today - timedelta(days=2)
    _weather(db, farm, start, 15)
    saved = client.put(
        f"/v1/blocks/{block_id}/seasons/{today.year}",
        headers=headers,
        json={"start_date": start.isoformat()},
    )
    assert saved.status_code == 200
    body = client.get(
        f"/v1/blocks/{block_id}/stages",
        headers=headers,
        params={"year": today.year},
    )
    assert body.status_code == 200
    payload = body.json()
    assert payload["setting"] is None
    assert payload["today"]["dd_counted"] is None
    assert all(row["label"] == "not_enough_data" for row in payload["stages"])
    assert all(row["reason"] == "phenology.no_gdd_setting" for row in payload["stages"])
    assert all(row["date"] is None for row in payload["stages"])
    assert all(row["dd_needed"] is None for row in payload["stages"])


def test_base_mismatch_is_setting_mismatch(
    client: TestClient,
    db: Session,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    load_catalog()
    user = make_user("mismatch@agrect.app", "seasons-password")
    farm = make_farm(user, "Mismatch", Decimal("36.7"), Decimal("3.1"))
    headers = auth_header(user)
    apple_id = _crop_id(client, headers, "apple")
    stage_id = _stages(client, headers, apple_id)[0]["id"]
    other_id = _stages(client, headers, apple_id)[1]["id"]
    created = client.post(
        f"/v1/farms/{farm.id}/blocks",
        headers=headers,
        json={"name": "North", "crop_id": apple_id},
    )
    block_id = created.json()["id"]
    _enter(
        client,
        farm,
        headers,
        apple_id,
        [
            {"stage_def_id": str(stage_id), "dd_value": "30", "base_c": "10", "method": "average"},
            {"stage_def_id": str(other_id), "dd_value": "50", "base_c": "10", "method": "average"},
        ],
    )
    today = _today(farm)
    start = today - timedelta(days=2)
    _weather(db, farm, start, 15)
    saved = client.put(
        f"/v1/blocks/{block_id}/seasons/{today.year}",
        headers=headers,
        json={"start_date": start.isoformat()},
    )
    assert saved.status_code == 200
    changed = client.put(
        f"/v1/farms/{farm.id}/gdd-settings/{apple_id}",
        headers=headers,
        json={"base_c": "4", "upper_c": None, "method": "average", "start_date": None},
    )
    assert changed.status_code == 200
    body = client.get(
        f"/v1/blocks/{block_id}/stages",
        headers=headers,
        params={"year": today.year},
    )
    assert body.status_code == 200
    rows = {row["stage"]["id"]: row for row in body.json()["stages"]}
    for stage in (stage_id, other_id):
        assert rows[str(stage)]["label"] == "not_enough_data"
        assert rows[str(stage)]["reason"] == "phenology.setting_mismatch"
        assert rows[str(stage)]["date"] is None
        assert rows[str(stage)]["dd_needed"] is None
        assert rows[str(stage)]["dd_source"] is None
    untouched = next(row for key, row in rows.items() if key not in {str(stage_id), str(other_id)})
    assert untouched["reason"] is None


def test_upper_mismatch_is_setting_mismatch(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    load_catalog()
    user = make_user("upper-mismatch@agrect.app", "seasons-password")
    farm = make_farm(user, "Upper", Decimal("36.7"), Decimal("3.1"))
    headers = auth_header(user)
    apple_id = _crop_id(client, headers, "apple")
    stages = _stages(client, headers, apple_id)
    matched = stages[0]["id"]
    mismatched = stages[1]["id"]
    created = client.post(
        f"/v1/farms/{farm.id}/blocks",
        headers=headers,
        json={"name": "North", "crop_id": apple_id},
    )
    block_id = created.json()["id"]
    setting = client.put(
        f"/v1/farms/{farm.id}/gdd-settings/{apple_id}",
        headers=headers,
        json={"base_c": "10", "upper_c": "30", "method": "average", "start_date": None},
    )
    assert setting.status_code == 200
    _enter(
        client,
        farm,
        headers,
        apple_id,
        [
            {
                "stage_def_id": str(matched),
                "dd_value": "30",
                "base_c": "10",
                "upper_c": "30",
                "method": "average",
            },
            {
                "stage_def_id": str(mismatched),
                "dd_value": "50",
                "base_c": "10",
                "upper_c": None,
                "method": "average",
            },
        ],
    )
    today = _today(farm)
    saved = client.put(
        f"/v1/blocks/{block_id}/seasons/{today.year}",
        headers=headers,
        json={"start_date": today.isoformat()},
    )
    assert saved.status_code == 200
    body = client.get(
        f"/v1/blocks/{block_id}/stages",
        headers=headers,
        params={"year": today.year},
    )
    assert body.status_code == 200
    payload = body.json()
    assert payload["history"]["status"] == payload["history_status"]
    assert isinstance(payload["history"]["years_count"], int)
    assert payload["season"]["start_date"] == today.isoformat()
    assert payload["season"]["start_stage"] is None
    assert payload["observations"] == []
    rows = {row["stage"]["id"]: row for row in payload["stages"]}
    used = rows[str(matched)]
    assert used["dd_needed"] == "30"
    assert used["dd_source"] == "entered"
    assert used["reason"] is None
    rejected = rows[str(mismatched)]
    assert rejected["label"] == "not_enough_data"
    assert rejected["reason"] == "phenology.setting_mismatch"
    assert rejected["date"] is None
    assert rejected["dd_needed"] is None
    assert rejected["dd_source"] is None


def test_scoping_is_404(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    load_catalog()
    owner = make_user("owner-season@agrect.app", "seasons-password")
    other = make_user("other-season@agrect.app", "seasons-password")
    farm = make_farm(owner, "Owned", Decimal("36.7"), Decimal("3.1"))
    headers = auth_header(owner)
    other_headers = auth_header(other)
    apple_id = _crop_id(client, headers, "apple")
    created = client.post(
        f"/v1/farms/{farm.id}/blocks",
        headers=headers,
        json={"name": "North", "crop_id": apple_id},
    )
    block_id = created.json()["id"]
    today = _today(farm)
    saved = client.put(
        f"/v1/blocks/{block_id}/seasons/{today.year}",
        headers=headers,
        json={"start_date": today.isoformat()},
    )
    assert saved.status_code == 200
    season_id = saved.json()["id"]
    stages = client.get(
        f"/v1/blocks/{block_id}/stages",
        headers=other_headers,
        params={"year": today.year},
    )
    assert stages.status_code == 404
    assert stages.json()["code"] == "block.not_found"
    denied = client.post(
        f"/v1/block-seasons/{season_id}/observations",
        headers=other_headers,
        json={"stage_def_id": str(uuid.uuid4()), "observed_on": today.isoformat()},
    )
    assert denied.status_code == 404
    assert denied.json()["code"] == "phenology.season_not_found"


def test_weather_refresh_moves_a_prediction(
    client: TestClient,
    db: Session,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    load_catalog()
    user = make_user("refresh-season@agrect.app", "seasons-password")
    farm = make_farm(user, "Refresh", Decimal("36.7"), Decimal("3.1"))
    farm.timezone = "Africa/Algiers"
    db.commit()
    headers = auth_header(user)
    apple_id = _crop_id(client, headers, "apple")
    stage_id = _stages(client, headers, apple_id)[0]["id"]
    created = client.post(
        f"/v1/farms/{farm.id}/blocks",
        headers=headers,
        json={"name": "North", "crop_id": apple_id},
    )
    block_id = created.json()["id"]
    assert (
        client.put(
            f"/v1/farms/{farm.id}/gdd-settings/{apple_id}",
            headers=headers,
            json={"base_c": "10", "upper_c": None, "method": "average", "start_date": None},
        ).status_code
        == 200
    )
    _enter(
        client,
        farm,
        headers,
        apple_id,
        [{"stage_def_id": str(stage_id), "dd_value": "30", "base_c": "10", "method": "average"}],
    )
    today = _today(farm)
    start = today - timedelta(days=2)
    _weather(db, farm, start, 15)
    assert (
        client.put(
            f"/v1/blocks/{block_id}/seasons/{today.year}",
            headers=headers,
            json={"start_date": start.isoformat()},
        ).status_code
        == 200
    )
    reached = start + timedelta(days=2)
    row = db.get(WeatherDaily, (farm.id, reached))
    assert row is not None
    row.tmin_c = Decimal("10")
    row.tmax_c = Decimal("10")
    db.commit()
    moved: list[object] = []

    def hear(payload: dict[str, object]) -> None:
        moved.append(payload.get("date"))

    subscribe("stage.predicted", hear)
    try:
        from app.core.events import publish

        publish("weather.daily_ready", {"db": db, "farm_id": farm.id, "from_date": start})
        db.commit()
    finally:
        unsubscribe("stage.predicted", hear)
    assert moved == [start + timedelta(days=3)]
    body = client.get(
        f"/v1/blocks/{block_id}/stages",
        headers=headers,
        params={"year": today.year},
    )
    assert body.status_code == 200
    first = next(row for row in body.json()["stages"] if row["stage"]["id"] == str(stage_id))
    assert first["date"] == (start + timedelta(days=3)).isoformat()
