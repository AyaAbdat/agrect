import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.auth.models import AppUser
from app.modules.catalog.loader import load_catalog
from app.modules.catalog.models import SoilTextureClass
from app.modules.farms.models import Farm
from app.modules.registry.models import FlowEntryMode, IrrigationLayout, IrrigationSystem, Valve
from app.modules.soilwater import calc
from app.modules.weather.models import WeatherDaily

_ZONE = ZoneInfo("Africa/Algiers")


def _today() -> datetime:
    return datetime.now(UTC).astimezone(_ZONE)


def _day(offset: int):
    return _today().date() + timedelta(days=offset)


def _owner(
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
    email: str,
) -> tuple[Farm, dict[str, str]]:
    user = make_user(email, "balance-password")
    farm = make_farm(user, "Farm", Decimal("36"), Decimal("3"))
    return farm, auth_header(user)


def _block(client: TestClient, farm: Farm, headers: dict[str, str], name: str = "North") -> str:
    created = client.post(f"/v1/farms/{farm.id}/blocks", headers=headers, json={"name": name})
    assert created.status_code == 201
    block_id = created.json()["id"]
    assert isinstance(block_id, str)
    return block_id


def _texture_id(db: Session) -> str:
    load_catalog()
    row = db.scalar(select(SoilTextureClass).where(SoilTextureClass.code == "loam"))
    assert row is not None
    return str(row.id)


def _weather(
    db: Session,
    farm: Farm,
    day,
    et0: str | None,
    rain: str,
    *,
    forecast: bool,
) -> None:
    db.add(
        WeatherDaily(
            farm_id=farm.id,
            date=day,
            rain_mm=None if rain is None else Decimal(rain),
            et0_mm=None if et0 is None else Decimal(et0),
            hours_count=24,
            is_forecast=forecast,
            source="estimated",
            inputs_hash="f" * 64,
        )
    )


def _layout_and_valves(db: Session, farm: Farm, block_id: str) -> list[str]:
    block_uuid = uuid.UUID(block_id)
    db.add(
        IrrigationLayout(
            farm_id=farm.id,
            block_id=block_uuid,
            system=IrrigationSystem.drip,
            entry_mode=FlowEntryMode.typed_flow,
            rate_mm_h=Decimal("20"),
            q_block_m3h=Decimal("40"),
        )
    )
    valves = [
        Valve(
            farm_id=farm.id,
            block_id=block_uuid,
            name="V1",
            sort=1,
            row_from=1,
            row_to=1,
            q_m3h=Decimal("25"),
        ),
        Valve(
            farm_id=farm.id,
            block_id=block_uuid,
            name="V2",
            sort=2,
            row_from=2,
            row_to=2,
            q_m3h=Decimal("15"),
        ),
    ]
    db.add_all(valves)
    db.commit()
    return [str(valve.id) for valve in valves]


def _soil(
    client: TestClient,
    block_id: str,
    headers: dict[str, str],
    texture: str,
    full_on: str | None,
) -> None:
    body: dict[str, object] = {
        "texture_mode": "class",
        "texture_class_id": texture,
        "root_depth_m": "1.0",
        "dry_down_pct": "50",
    }
    if full_on is not None:
        body["full_on"] = full_on
    saved = client.put(f"/v1/blocks/{block_id}/soil", headers=headers, json=body)
    assert saved.status_code == 200


def _settings(
    client: TestClient,
    block_id: str,
    headers: dict[str, str],
    *,
    kc: str | None,
    if_match: str | None = None,
    reason: str | None = None,
) -> None:
    body: dict[str, object] = {"efficiency": "1", "kc_source": "entered"}
    if kc is not None:
        body["kc"] = kc
    if reason is not None:
        body["reason"] = reason
    headers_out = headers if if_match is None else {**headers, "If-Match": if_match}
    saved = client.put(
        f"/v1/blocks/{block_id}/irrigation-settings",
        headers=headers_out,
        json=body,
    )
    assert saved.status_code == 200, saved.json()


def _row(body: dict[str, object], day) -> dict[str, object]:
    rows = body["rows"]
    assert isinstance(rows, list)
    found = next(row for row in rows if row["date"] == day.isoformat())
    assert isinstance(found, dict)
    return found


def _dec(row: dict[str, object], field: str) -> Decimal | None:
    value = row[field]
    if value is None:
        return None
    assert isinstance(value, str)
    return Decimal(value)


def test_five_day_balance_recomputes_forward(
    client: TestClient,
    db: Session,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm, headers = _owner(make_user, make_farm, auth_header, "balance@agrect.app")
    block_id = _block(client, farm, headers)
    d1, d2, d3, d4, d5 = (_day(-5), _day(-4), _day(-3), _day(-2), _day(-1))
    today = _day(0)
    for day, rain in ((d1, "0"), (d2, "0"), (d3, "10"), (d4, "0"), (d5, "0")):
        _weather(db, farm, day, "6", rain, forecast=False)
    _weather(db, farm, today, "7", "0", forecast=True)
    valve_ids = _layout_and_valves(db, farm, block_id)
    texture = _texture_id(db)
    _soil(client, block_id, headers, texture, d1.isoformat())
    _settings(client, block_id, headers, kc="1")

    window = {"from": d1.isoformat(), "to": d5.isoformat()}
    before = client.get(f"/v1/blocks/{block_id}/water-balance", headers=headers, params=window)
    assert before.status_code == 200
    baseline = before.json()
    assert baseline["notes"] == []
    assert [_dec(_row(baseline, day), "depletion_mm") for day in (d1, d2, d3, d4, d5)] == [
        Decimal("6"),
        Decimal("12"),
        Decimal("8"),
        Decimal("14"),
        Decimal("20"),
    ]
    assert _dec(_row(baseline, d3), "drainage_mm") == Decimal("0")
    day1_hash = _row(baseline, d1)["inputs_hash"]
    assert isinstance(day1_hash, str)
    assert len(day1_hash) == 64

    start = datetime.combine(d2, datetime.min.time(), tzinfo=_ZONE).replace(hour=8)
    logged = client.post(
        f"/v1/blocks/{block_id}/irrigation-events",
        headers=headers,
        json={"valve_ids": valve_ids, "start_at": start.isoformat(), "duration_min": 90},
    )
    assert logged.status_code == 200
    assert logged.headers["etag"] == "1"
    event = logged.json()
    assert Decimal(event["depth_mm"]) == Decimal("30")
    assert Decimal(event["volume_m3"]) == Decimal("60")
    assert Decimal(event["soil_mm"]) == Decimal("30")
    assert Decimal(event["runoff_mm"]) == Decimal("0")
    assert event["source"] == "calculated"
    event_id = event["id"]

    after = client.get(f"/v1/blocks/{block_id}/water-balance", headers=headers, params=window)
    assert after.status_code == 200
    updated = after.json()
    assert _row(updated, d1)["inputs_hash"] == day1_hash
    assert _dec(_row(updated, d1), "depletion_mm") == Decimal("6")
    assert [_dec(_row(updated, day), "depletion_mm") for day in (d2, d3, d4, d5)] == [
        Decimal("0"),
        Decimal("0"),
        Decimal("6"),
        Decimal("12"),
    ]
    assert _dec(_row(updated, d2), "drainage_mm") == Decimal("18")
    assert _dec(_row(updated, d3), "drainage_mm") == Decimal("4")
    assert _row(updated, d1)["status"] == "ok"
    assert _row(updated, d1)["is_forecast"] is False

    today_body = client.get(f"/v1/blocks/{block_id}/irrigation-today", headers=headers)
    assert today_body.status_code == 200
    advice = today_body.json()
    assert advice["date"] == today.isoformat()
    assert Decimal(advice["depletion_mm"]) == Decimal("12")
    assert Decimal(advice["taw_mm"]) == Decimal("130")
    assert Decimal(advice["raw_mm"]) == Decimal("65")
    assert Decimal(advice["etc_today_mm"]) == Decimal("7")
    assert Decimal(advice["water_left_mm"]) == Decimal("118")
    assert Decimal(advice["irrigate_below_mm"]) == Decimal("65")
    assert Decimal(_row(updated, d1)["water_left_mm"]) == Decimal("124")
    assert Decimal(_row(updated, d5)["water_left_mm"]) == Decimal("118")
    assert Decimal(_row(updated, d5)["irrigate_below_mm"]) == Decimal("65")
    soil = client.get(f"/v1/blocks/{block_id}/soil", headers=headers)
    assert soil.status_code == 200
    assert Decimal(soil.json()["water_left_mm"]) == Decimal("118")
    assert Decimal(soil.json()["irrigate_below_mm"]) == Decimal("65")
    assert advice["status"] == "ok"
    assert advice["recommended"] == "maintain"
    assert advice["label"] == "calculated"
    assert advice["missing"] == []
    assert Decimal(advice["refill"]["net_mm"]) == Decimal("19")
    assert Decimal(advice["refill"]["gross_mm"]) == Decimal("19")
    assert Decimal(advice["refill"]["run_time_min"]) == Decimal("57")
    assert Decimal(advice["refill"]["volume_m3"]) == Decimal("38")
    assert Decimal(advice["maintain"]["net_mm"]) == Decimal("7")
    assert Decimal(advice["maintain"]["gross_mm"]) == Decimal("7")
    assert Decimal(advice["maintain"]["run_time_min"]) == Decimal("21")
    assert Decimal(advice["maintain"]["volume_m3"]) == Decimal("14")

    farm_today = client.get(f"/v1/farms/{farm.id}/irrigation-today", headers=headers)
    assert farm_today.status_code == 200
    farm_body = farm_today.json()
    assert farm_body["date"] == today.isoformat()
    assert len(farm_body["blocks"]) == 1
    assert farm_body["blocks"][0]["block_id"] == block_id
    assert Decimal(farm_body["blocks"][0]["depletion_mm"]) == Decimal("12")
    assert farm_body["blocks"][0]["recommended"] == "maintain"
    assert Decimal(farm_body["blocks"][0]["water_left_mm"]) == Decimal("118")
    assert Decimal(farm_body["blocks"][0]["irrigate_below_mm"]) == Decimal("65")

    checked = client.post(
        f"/v1/blocks/{block_id}/soil-checks",
        headers=headers,
        json={"date": d4.isoformat(), "depth_band": "0_30", "feel": "dry"},
    )
    assert checked.status_code == 200
    assert Decimal(checked.json()["reset_depletion_mm"]) == Decimal("113.75")
    reset = client.get(f"/v1/blocks/{block_id}/water-balance", headers=headers, params=window)
    reset_body = reset.json()
    assert _dec(_row(reset_body, d2), "depletion_mm") == Decimal("0")
    assert _dec(_row(reset_body, d3), "depletion_mm") == Decimal("0")
    assert _dec(_row(reset_body, d4), "depletion_mm") == Decimal("113.75")
    assert _row(reset_body, d4)["status"] == "irrigate_soon"
    assert _dec(_row(reset_body, d5), "depletion_mm") == Decimal("119.75")

    missing_match = client.delete(
        f"/v1/blocks/{block_id}/irrigation-events/{event_id}",
        headers=headers,
    )
    assert missing_match.status_code == 428
    removed = client.delete(
        f"/v1/blocks/{block_id}/irrigation-events/{event_id}",
        headers={**headers, "If-Match": "1"},
    )
    assert removed.status_code == 204
    restored = client.get(f"/v1/blocks/{block_id}/water-balance", headers=headers, params=window)
    restored_body = restored.json()
    assert _dec(_row(restored_body, d2), "depletion_mm") == Decimal("12")
    assert _dec(_row(restored_body, d4), "depletion_mm") == Decimal("113.75")
    listed = client.get(f"/v1/blocks/{block_id}/irrigation-events", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["events"] == []
    assert listed.json()["totals"]["count"] == 0


def test_patch_recomputes_depth_and_requires_if_match(
    client: TestClient,
    db: Session,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm, headers = _owner(make_user, make_farm, auth_header, "patch@agrect.app")
    block_id = _block(client, farm, headers, "South")
    _weather(db, farm, _day(-1), "6", "0", forecast=False)
    db.commit()
    valve_ids = _layout_and_valves(db, farm, block_id)
    _soil(client, block_id, headers, _texture_id(db), _day(-1).isoformat())
    _settings(client, block_id, headers, kc="1")
    not_ready = client.post(
        f"/v1/blocks/{uuid.uuid4()}/irrigation-events",
        headers=headers,
        json={
            "valve_ids": [str(uuid.uuid4())],
            "start_at": _today().isoformat(),
            "duration_min": 90,
        },
    )
    assert not_ready.status_code == 404
    bare = _block(client, farm, headers, "Bare")
    unready = client.post(
        f"/v1/blocks/{bare}/irrigation-events",
        headers=headers,
        json={"valve_ids": valve_ids, "start_at": _today().isoformat(), "duration_min": 90},
    )
    assert unready.status_code == 422
    assert unready.json()["fields"]["valve_ids"] == "irrigation.valve_not_found"
    own = Valve(
        farm_id=farm.id,
        block_id=uuid.UUID(bare),
        name="V1",
        sort=1,
        row_from=1,
        row_to=1,
        q_m3h=Decimal("40"),
    )
    db.add(own)
    db.commit()
    missing_rate = client.post(
        f"/v1/blocks/{bare}/irrigation-events",
        headers=headers,
        json={
            "valve_ids": [str(own.id)],
            "start_at": _today().isoformat(),
            "duration_min": 90,
        },
    )
    assert missing_rate.status_code == 422
    assert missing_rate.json()["fields"]["irrigation"] == "irrigation.block_not_ready"
    no_layout = client.post(
        f"/v1/blocks/{bare}/irrigation-events",
        headers=headers,
        json={
            "valve_ids": [str(uuid.uuid4())],
            "start_at": _today().isoformat(),
            "duration_min": 90,
        },
    )
    assert no_layout.status_code == 422
    assert no_layout.json()["fields"]["valve_ids"] == "irrigation.valve_not_found"

    start = datetime.combine(_day(-1), datetime.min.time(), tzinfo=_ZONE).replace(hour=9)
    created = client.post(
        f"/v1/blocks/{block_id}/irrigation-events",
        headers=headers,
        json={"valve_ids": valve_ids, "start_at": start.isoformat(), "duration_min": 90},
    )
    assert created.status_code == 200
    event_id = created.json()["id"]
    skipped = client.patch(
        f"/v1/blocks/{block_id}/irrigation-events/{event_id}",
        headers=headers,
        json={"duration_min": 60},
    )
    assert skipped.status_code == 428
    patched = client.patch(
        f"/v1/blocks/{block_id}/irrigation-events/{event_id}",
        headers={**headers, "If-Match": "1"},
        json={"duration_min": 60},
    )
    assert patched.status_code == 200
    assert patched.headers["etag"] == "2"
    assert Decimal(patched.json()["depth_mm"]) == Decimal("20")
    assert Decimal(patched.json()["volume_m3"]) == Decimal("40")
    assert Decimal(patched.json()["soil_mm"]) == Decimal("20")


def test_no_data_without_kc_and_restart_after_a_gap(
    client: TestClient,
    db: Session,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm, headers = _owner(make_user, make_farm, auth_header, "gap@agrect.app")
    block_id = _block(client, farm, headers)
    d1, d2, d3 = _day(-3), _day(-2), _day(-1)
    _weather(db, farm, d1, "6", "0", forecast=False)
    _weather(db, farm, d2, None, "0", forecast=False)
    _weather(db, farm, d3, "6", "0", forecast=False)
    db.commit()
    texture = _texture_id(db)
    _soil(client, block_id, headers, texture, None)
    _settings(client, block_id, headers, kc=None)
    missing_kc = client.get(
        f"/v1/blocks/{block_id}/water-balance",
        headers=headers,
        params={"from": d1.isoformat(), "to": d3.isoformat()},
    )
    assert missing_kc.status_code == 200
    without_kc = missing_kc.json()
    assert without_kc["notes"] == [f"assumed at field capacity on {d1.isoformat()}"]
    assert all(row["status"] == "no_data" for row in without_kc["rows"])
    assert all(row["depletion_mm"] is None for row in without_kc["rows"])
    assert _row(without_kc, d1)["water_left_mm"] is None
    assert Decimal(_row(without_kc, d1)["irrigate_below_mm"]) == Decimal("65")

    _settings(client, block_id, headers, kc="1", if_match="1", reason="add kc")
    filled = client.get(
        f"/v1/blocks/{block_id}/water-balance",
        headers=headers,
        params={"from": d1.isoformat(), "to": d3.isoformat()},
    )
    body = filled.json()
    assert f"assumed at field capacity on {d1.isoformat()}" in body["notes"]
    assert f"restarted at field capacity on {d3.isoformat()}" in body["notes"]
    assert _dec(_row(body, d1), "depletion_mm") == Decimal("6")
    assert _row(body, d2)["status"] == "no_data"
    assert _row(body, d2)["depletion_mm"] is None
    assert _dec(_row(body, d3), "depletion_mm") == Decimal("6")


def test_balance_routes_are_farm_scoped(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm, headers = _owner(make_user, make_farm, auth_header, "owner-balance@agrect.app")
    other = make_user("other-balance@agrect.app", "password-b")
    other_headers = auth_header(other)
    block_id = _block(client, farm, headers)
    event_id = uuid.uuid4()
    paths = [
        ("get", f"/v1/blocks/{block_id}/irrigation-events", None),
        ("get", f"/v1/blocks/{block_id}/water-balance", None),
        ("get", f"/v1/blocks/{block_id}/irrigation-today", None),
        ("get", f"/v1/farms/{farm.id}/irrigation-today", None),
    ]
    for method, path, _body in paths:
        response = client.request(method, path, headers=other_headers)
        assert response.status_code == 404
        assert response.json()["code"] in {"block.not_found", "farm.not_found"}
    foreign_post = client.post(
        f"/v1/blocks/{block_id}/irrigation-events",
        headers=other_headers,
        json={
            "valve_ids": [str(uuid.uuid4())],
            "start_at": _today().isoformat(),
            "duration_min": 30,
        },
    )
    assert foreign_post.status_code == 404
    assert foreign_post.json() == {"code": "block.not_found"}
    foreign_check = client.post(
        f"/v1/blocks/{block_id}/soil-checks",
        headers=other_headers,
        json={"date": _day(0).isoformat(), "depth_band": "30_60", "feel": "moist"},
    )
    assert foreign_check.status_code == 404
    foreign_patch = client.patch(
        f"/v1/blocks/{block_id}/irrigation-events/{event_id}",
        headers={**other_headers, "If-Match": "1"},
        json={"duration_min": 15},
    )
    assert foreign_patch.status_code == 404
    foreign_delete = client.delete(
        f"/v1/blocks/{block_id}/irrigation-events/{event_id}",
        headers={**other_headers, "If-Match": "1"},
    )
    assert foreign_delete.status_code == 404


def test_irrigation_events_return_latest_first(
    client: TestClient,
    db: Session,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm, headers = _owner(make_user, make_farm, auth_header, "events@agrect.app")
    block_id = _block(client, farm, headers)
    valve_ids = _layout_and_valves(db, farm, block_id)
    _settings(client, block_id, headers, kc="1")
    earlier = datetime.combine(_day(-2), datetime.min.time(), tzinfo=_ZONE).replace(hour=8)
    later = datetime.combine(_day(-1), datetime.min.time(), tzinfo=_ZONE).replace(hour=9)
    created_ids: list[str] = []
    for start in (earlier, later):
        created = client.post(
            f"/v1/blocks/{block_id}/irrigation-events",
            headers=headers,
            json={"valve_ids": valve_ids, "start_at": start.isoformat(), "duration_min": 30},
        )
        assert created.status_code == 200
        event_id = created.json()["id"]
        assert isinstance(event_id, str)
        created_ids.append(event_id)
    listed = client.get(
        f"/v1/blocks/{block_id}/irrigation-events",
        headers=headers,
        params={"limit": 1},
    )
    assert listed.status_code == 200
    body = listed.json()
    assert len(body["events"]) == 1
    assert body["events"][0]["id"] == created_ids[1]
    assert body["totals"]["count"] == 2
    full = client.get(f"/v1/blocks/{block_id}/irrigation-events", headers=headers)
    assert [row["id"] for row in full.json()["events"]] == [created_ids[1], created_ids[0]]


def test_irrigation_preview_matches_saved_event_and_writes_nothing(
    client: TestClient,
    db: Session,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm, headers = _owner(make_user, make_farm, auth_header, "preview@agrect.app")
    block_id = _block(client, farm, headers, "North orchard")
    valve_ids = _layout_and_valves(db, farm, block_id)
    layout = db.scalar(
        select(IrrigationLayout).where(IrrigationLayout.block_id == uuid.UUID(block_id))
    )
    assert layout is not None
    rate = (Decimal(40) / (Decimal(10) * Decimal("1.5"))).quantize(Decimal("0.0001"))
    layout.rate_mm_h = rate
    db.commit()
    saved = client.put(
        f"/v1/blocks/{block_id}/irrigation-settings",
        headers=headers,
        json={"efficiency": "0.9", "kc": "1", "kc_source": "entered"},
    )
    assert saved.status_code == 200
    body = {
        "block_id": block_id,
        "valve_ids": valve_ids,
        "duration_min": 90,
    }
    anonymous = client.post("/v1/calc/soilwater/irrigation", json=body)
    assert anonymous.status_code == 401
    other = make_user("preview-other@agrect.app", "password-b")
    foreign = client.post(
        "/v1/calc/soilwater/irrigation",
        headers=auth_header(other),
        json=body,
    )
    assert foreign.status_code == 404
    assert foreign.json() == {"code": "block.not_found"}
    missing = client.post(
        "/v1/calc/soilwater/irrigation",
        headers=headers,
        json={**body, "block_id": str(uuid.uuid4())},
    )
    assert missing.status_code == 404
    assert missing.json() == {"code": "block.not_found"}

    preview = client.post("/v1/calc/soilwater/irrigation", headers=headers, json=body)
    assert preview.status_code == 200
    shown = preview.json()
    depth = calc.depth_mm(rate, Decimal(90))
    volume = calc.volume_m3(Decimal(40), Decimal(90))
    soil_mm, runoff_mm = calc.soil_entering(rate, Decimal(90), Decimal("0.9"))
    assert volume == Decimal(60)
    assert depth.quantize(Decimal("0.01")) == Decimal("4.00")
    assert soil_mm == depth * Decimal("0.9")
    assert Decimal(shown["depth_mm"]) == depth
    assert Decimal(shown["volume_m3"]) == volume
    assert Decimal(shown["soil_mm"]) == soil_mm
    assert Decimal(shown["runoff_mm"]) == runoff_mm
    assert shown["source"] == "calculated"
    untouched = client.get(f"/v1/blocks/{block_id}/irrigation-events", headers=headers)
    assert untouched.json()["totals"]["count"] == 0

    bare = _block(client, farm, headers, "Bare preview")
    unready = client.post(
        "/v1/calc/soilwater/irrigation",
        headers=headers,
        json={"block_id": bare, "valve_ids": valve_ids, "duration_min": 90},
    )
    assert unready.status_code == 422
    assert unready.json()["fields"]["valve_ids"] == "irrigation.valve_not_found"
    own = Valve(
        farm_id=farm.id,
        block_id=uuid.UUID(bare),
        name="V1",
        sort=1,
        row_from=1,
        row_to=1,
        q_m3h=Decimal("40"),
    )
    db.add(own)
    db.commit()
    not_ready = client.post(
        "/v1/calc/soilwater/irrigation",
        headers=headers,
        json={"block_id": bare, "valve_ids": [str(own.id)], "duration_min": 90},
    )
    assert not_ready.status_code == 422
    assert not_ready.json()["fields"]["irrigation"] == "irrigation.block_not_ready"

    start = datetime.combine(_day(0), datetime.min.time(), tzinfo=_ZONE).replace(hour=8)
    logged = client.post(
        f"/v1/blocks/{block_id}/irrigation-events",
        headers=headers,
        json={"valve_ids": valve_ids, "start_at": start.isoformat(), "duration_min": 90},
    )
    assert logged.status_code == 200
    event = logged.json()
    assert Decimal(event["depth_mm"]) == Decimal(shown["depth_mm"])
    assert Decimal(event["volume_m3"]) == Decimal("60")
    assert Decimal(event["soil_mm"]) == Decimal(shown["soil_mm"])
    assert event["source"] == "calculated"


def test_irrigation_event_window_totals(
    client: TestClient,
    db: Session,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm, headers = _owner(make_user, make_farm, auth_header, "totals@agrect.app")
    block_id = _block(client, farm, headers)
    valve_ids = _layout_and_valves(db, farm, block_id)
    _settings(client, block_id, headers, kc="1")
    early = datetime.combine(_day(-3), datetime.min.time(), tzinfo=_ZONE).replace(hour=7)
    late = datetime.combine(_day(-1), datetime.min.time(), tzinfo=_ZONE).replace(hour=7)
    for start, minutes in ((early, 90), (late, 30)):
        created = client.post(
            f"/v1/blocks/{block_id}/irrigation-events",
            headers=headers,
            json={"valve_ids": valve_ids, "start_at": start.isoformat(), "duration_min": minutes},
        )
        assert created.status_code == 200
    window = client.get(
        f"/v1/blocks/{block_id}/irrigation-events",
        headers=headers,
        params={"from": _day(-3).isoformat(), "to": _day(-2).isoformat()},
    )
    assert window.status_code == 200
    body = window.json()
    assert len(body["events"]) == 1
    assert body["events"][0]["duration_min"] == 90
    assert body["totals"]["count"] == 1
    assert Decimal(body["totals"]["depth_mm"]) == Decimal(30)
    assert Decimal(body["totals"]["volume_m3"]) == Decimal(60)
    assert Decimal(body["totals"]["soil_mm"]) == Decimal(30)
    full = client.get(f"/v1/blocks/{block_id}/irrigation-events", headers=headers)
    totals = full.json()["totals"]
    assert totals["count"] == 2
    assert Decimal(totals["depth_mm"]) == Decimal(40)
    assert Decimal(totals["volume_m3"]) == Decimal(80)
    assert Decimal(totals["soil_mm"]) == Decimal(40)


def test_soil_check_preview_percent_and_missing_taw(
    client: TestClient,
    db: Session,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm, headers = _owner(make_user, make_farm, auth_header, "feel@agrect.app")
    block_id = _block(client, farm, headers)
    missing = client.post(
        f"/v1/blocks/{block_id}/soil-checks/preview",
        headers=headers,
        json={"feel": "moist"},
    )
    assert missing.status_code == 422
    assert missing.json()["fields"]["taw_mm"] == "soil.taw_missing"
    _soil(client, block_id, headers, _texture_id(db), _day(-1).isoformat())
    before = client.get(f"/v1/blocks/{block_id}/water-balance", headers=headers)
    preview = client.post(
        f"/v1/blocks/{block_id}/soil-checks/preview",
        headers=headers,
        json={"feel": "moist"},
    )
    assert preview.status_code == 200
    body = preview.json()
    taw = Decimal(130)
    assert Decimal(body["water_left_mm"]) == taw * Decimal("0.625")
    assert Decimal(body["reset_depletion_mm"]) == taw * Decimal("0.375")
    assert Decimal(body["pct_of_taw"]) == Decimal("62.5")
    after = client.get(f"/v1/blocks/{block_id}/water-balance", headers=headers)
    assert after.json() == before.json()


def test_water_balance_period_week_month_and_season(
    client: TestClient,
    db: Session,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm, headers = _owner(make_user, make_farm, auth_header, "period@agrect.app")
    block_id = _block(client, farm, headers)
    today = _day(0)
    full_on = _day(-8)
    _weather(db, farm, full_on, "5", "0", forecast=False)
    _weather(db, farm, today, "6", "0", forecast=True)
    db.commit()
    _soil(client, block_id, headers, _texture_id(db), full_on.isoformat())
    _settings(client, block_id, headers, kc="1")

    week = client.get(
        f"/v1/blocks/{block_id}/water-balance",
        headers=headers,
        params={"period": "week"},
    )
    assert week.status_code == 200
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    week_dates = [row["date"] for row in week.json()["rows"]]
    assert week_dates
    assert all(week_start.isoformat() <= day <= week_end.isoformat() for day in week_dates)
    assert full_on.isoformat() not in week_dates
    assert today.isoformat() in week_dates

    month = client.get(
        f"/v1/blocks/{block_id}/water-balance",
        headers=headers,
        params={"period": "month"},
    )
    assert month.status_code == 200
    month_start = today.replace(day=1)
    if month_start.month == 12:
        next_month = month_start.replace(year=month_start.year + 1, month=1)
    else:
        next_month = month_start.replace(month=month_start.month + 1)
    month_end = next_month - timedelta(days=1)
    month_dates = [row["date"] for row in month.json()["rows"]]
    assert all(month_start.isoformat() <= day <= month_end.isoformat() for day in month_dates)

    season = client.get(
        f"/v1/blocks/{block_id}/water-balance",
        headers=headers,
        params={"period": "season"},
    )
    assert season.status_code == 200
    season_dates = [row["date"] for row in season.json()["rows"]]
    assert season_dates[0] == full_on.isoformat()
    assert today.isoformat() in season_dates

    open_ended = client.get(
        f"/v1/blocks/{block_id}/water-balance",
        headers=headers,
        params={"from": full_on.isoformat(), "to": today.isoformat()},
    )
    assert [row["date"] for row in open_ended.json()["rows"]] == season_dates

    invalid = client.get(
        f"/v1/blocks/{block_id}/water-balance",
        headers=headers,
        params={"period": "year"},
    )
    assert invalid.status_code == 422


def test_season_without_full_on_starts_at_first_balance_day(
    client: TestClient,
    db: Session,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm, headers = _owner(make_user, make_farm, auth_header, "season@agrect.app")
    block_id = _block(client, farm, headers)
    first = _day(-4)
    _weather(db, farm, first, "4", "0", forecast=False)
    _weather(db, farm, _day(0), "4", "0", forecast=True)
    db.commit()
    _soil(client, block_id, headers, _texture_id(db), None)
    _settings(client, block_id, headers, kc="1")
    season = client.get(
        f"/v1/blocks/{block_id}/water-balance",
        headers=headers,
        params={"period": "season"},
    )
    assert season.status_code == 200
    dates = [row["date"] for row in season.json()["rows"]]
    assert dates[0] == first.isoformat()
    assert _day(0).isoformat() in dates
