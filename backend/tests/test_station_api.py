import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.auth.models import AppUser
from app.modules.catalog.loader import load_catalog
from app.modules.catalog.models import SoilTextureClass
from app.modules.farms.models import Farm
from app.modules.soilwater import calc as soil_calc
from app.modules.soilwater.models import IrrigationEvent
from app.modules.station.models import CapacityDecision
from app.modules.weather.models import WeatherDaily
from tests.test_blocks_geo import rectangle

_ZONE = ZoneInfo("Africa/Algiers")


def _today():
    return datetime.now(UTC).astimezone(_ZONE).date()


def _owner(
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
    email: str,
) -> tuple[Farm, dict[str, str]]:
    user = make_user(email, "station-password")
    farm = make_farm(user, "Farm", Decimal("36"), Decimal("3"))
    return farm, auth_header(user)


def _crop_id(client: TestClient, headers: dict[str, str]) -> str:
    load_catalog()
    crops = client.get("/v1/catalog/crops", headers=headers)
    assert crops.status_code == 200
    return next(row["id"] for row in crops.json() if row["code"] == "olive")


def _put(
    client: TestClient,
    path: str,
    headers: dict[str, str],
    version: int,
    body: dict[str, object],
):
    return client.put(path, headers={**headers, "If-Match": str(version)}, json=body)


def _complete_block(
    client: TestClient,
    farm: Farm,
    headers: dict[str, str],
    *,
    name: str,
    rows_total: int,
    flow_m3h: str,
    valves: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    created = client.post(
        f"/v1/farms/{farm.id}/blocks",
        headers=headers,
        json={
            "name": name,
            "outline": rectangle(36.0, 3.0, 102, 102),
            "net_area_ha": "1",
            "crop_id": _crop_id(client, headers),
            "rows_total": rows_total,
        },
    )
    assert created.status_code == 201, created.text
    block_id = created.json()["id"]
    version = int(created.json()["version"])
    planted = _put(
        client,
        f"/v1/blocks/{block_id}/plantings",
        headers,
        version,
        {
            "plantings": [
                {
                    "density_input": "spacing",
                    "row_spacing_m": "4.00",
                    "tree_spacing_m": "2.00",
                }
            ]
        },
    )
    assert planted.status_code == 200, planted.text
    laid = _put(
        client,
        f"/v1/blocks/{block_id}/irrigation-layout",
        headers,
        int(planted.json()["version"]),
        {
            "system": "drip",
            "entry_mode": "typed_flow",
            "typed_flow_basis": "block",
            "typed_flow_m3h": flow_m3h,
        },
    )
    assert laid.status_code == 200, laid.text
    version = int(laid.json()["version"])
    if valves is not None:
        split = _put(
            client,
            f"/v1/blocks/{block_id}/valves",
            headers,
            version,
            {"valves": valves},
        )
        assert split.status_code == 200, split.text
        version = int(split.json()["version"])
    done = client.post(
        f"/v1/blocks/{block_id}/complete",
        headers={**headers, "If-Match": str(version)},
    )
    assert done.status_code == 200, done.text
    body = done.json()
    assert isinstance(body, dict)
    return body


def _weather(
    db: Session,
    farm: Farm,
    day,
    et0: str | None,
    *,
    forecast: bool,
) -> None:
    db.add(
        WeatherDaily(
            farm_id=farm.id,
            date=day,
            et0_mm=None if et0 is None else Decimal(et0),
            rain_mm=Decimal("0"),
            hours_count=24,
            is_forecast=forecast,
            source="estimated",
            inputs_hash="a" * 64,
        )
    )


def test_pump_crud_requires_if_match(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm, headers = _owner(make_user, make_farm, auth_header, "pumps@agrect.app")
    empty = client.get(f"/v1/farms/{farm.id}/station", headers=headers)
    assert empty.status_code == 200
    assert empty.json()["station"] is None
    assert empty.json()["pumps"] == []
    assert empty.json()["totals"]["pumps_flow_m3h"] == "0"

    refused = client.post(
        f"/v1/farms/{farm.id}/station/pumps",
        headers=headers,
        json={"name": "North", "flow_m3h": "0"},
    )
    assert refused.status_code == 422
    assert refused.json()["fields"]["flow_m3h"] == "station.flow_must_be_positive"

    created = client.post(
        f"/v1/farms/{farm.id}/station/pumps",
        headers=headers,
        json={"name": "North", "flow_m3h": "30"},
    )
    assert created.status_code == 201, created.text
    assert created.headers["etag"] == "1"
    pump_id = created.json()["id"]
    assert created.json()["serves_all_blocks"] is True
    assert created.json()["pressure_bar"] is None
    assert created.json()["windows"] == []
    assert created.json()["blocks"] == []

    taken = client.post(
        f"/v1/farms/{farm.id}/station/pumps",
        headers=headers,
        json={"name": "North", "flow_m3h": "12"},
    )
    assert taken.status_code == 422
    assert taken.json()["fields"]["name"] == "station.name_taken"

    missing = client.patch(
        f"/v1/pumps/{pump_id}",
        headers=headers,
        json={"name": "South"},
    )
    assert missing.status_code == 428
    assert missing.json() == {"code": "conflict.version_required"}
    stale = client.patch(
        f"/v1/pumps/{pump_id}",
        headers={**headers, "If-Match": "9"},
        json={"name": "South"},
    )
    assert stale.status_code == 409
    assert stale.json() == {"code": "conflict.version"}
    renamed = client.patch(
        f"/v1/pumps/{pump_id}",
        headers={**headers, "If-Match": "1"},
        json={"name": "South", "pressure_bar": "2.5"},
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.headers["etag"] == "2"
    assert renamed.json()["name"] == "South"
    assert renamed.json()["pressure_bar"] == "2.5"
    assert renamed.json()["flow_m3h"] == "30"

    listed = client.get(f"/v1/farms/{farm.id}/station", headers=headers)
    assert listed.status_code == 200
    body = listed.json()
    assert body["station"]["name"] == "Station"
    assert body["totals"]["pumps_flow_m3h"] == "30"
    assert body["pumps"][0]["id"] == pump_id

    no_match = client.delete(f"/v1/pumps/{pump_id}", headers=headers)
    assert no_match.status_code == 428
    removed = client.delete(
        f"/v1/pumps/{pump_id}",
        headers={**headers, "If-Match": "2"},
    )
    assert removed.status_code == 204
    after = client.get(f"/v1/farms/{farm.id}/station", headers=headers)
    assert after.json()["pumps"] == []
    assert after.json()["station"]["name"] == "Station"
    assert after.json()["totals"]["pumps_flow_m3h"] == "0"


def test_windows_and_blocks_a_pump_serves(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm, headers = _owner(make_user, make_farm, auth_header, "windows@agrect.app")
    other_user = make_user("windows-b@agrect.app", "station-password")
    other_farm = make_farm(other_user, "Other", Decimal("36"), Decimal("3"))
    other_block = client.post(
        f"/v1/farms/{other_farm.id}/blocks",
        headers=auth_header(other_user),
        json={"name": "Foreign"},
    )
    assert other_block.status_code == 201
    own = client.post(
        f"/v1/farms/{farm.id}/blocks",
        headers=headers,
        json={"name": "North"},
    )
    assert own.status_code == 201
    block_id = own.json()["id"]
    created = client.post(
        f"/v1/farms/{farm.id}/station/pumps",
        headers=headers,
        json={"name": "P1", "flow_m3h": "18"},
    )
    assert created.status_code == 201, created.text
    pump_id = created.json()["id"]

    invalid = client.put(
        f"/v1/pumps/{pump_id}/windows",
        headers={**headers, "If-Match": "1"},
        json={"windows": [{"start_time": "25:00", "end_time": "06:00"}]},
    )
    assert invalid.status_code == 422
    assert invalid.json()["fields"]["windows"] == "station.window_invalid"

    saved = client.put(
        f"/v1/pumps/{pump_id}/windows",
        headers={**headers, "If-Match": "1"},
        json={
            "windows": [
                {"start_time": "22:00", "end_time": "06:00"},
                {"start_time": "08:00", "end_time": "08:00"},
            ]
        },
    )
    assert saved.status_code == 200, saved.text
    assert saved.headers["etag"] == "2"
    windows = {(row["start_time"][:5], row["end_time"][:5]) for row in saved.json()["windows"]}
    assert windows == {("22:00", "06:00"), ("08:00", "08:00")}

    foreign = client.put(
        f"/v1/pumps/{pump_id}/blocks",
        headers={**headers, "If-Match": "2"},
        json={"block_ids": [other_block.json()["id"]]},
    )
    assert foreign.status_code == 422
    assert foreign.json()["fields"]["block_ids"] == "station.block_not_in_farm"

    limited = client.put(
        f"/v1/pumps/{pump_id}/blocks",
        headers={**headers, "If-Match": "2"},
        json={"block_ids": [block_id]},
    )
    assert limited.status_code == 200, limited.text
    assert limited.headers["etag"] == "3"
    assert limited.json()["serves_all_blocks"] is False
    assert limited.json()["blocks"] == [{"id": block_id, "name": "North"}]

    source = client.post(
        f"/v1/farms/{farm.id}/water-sources",
        headers=headers,
        json={"name": "Bore", "kind": "borehole"},
    )
    assert source.status_code == 201, source.text
    assert source.json()["ec_ds_m"] is None
    source_id = source.json()["id"]
    patched = client.patch(
        f"/v1/water-sources/{source_id}",
        headers=headers,
        json={"ec_ds_m": "1.8", "basin_volume_m3": None},
    )
    assert patched.status_code == 200
    assert patched.json()["ec_ds_m"] == "1.8"
    linked = client.patch(
        f"/v1/pumps/{pump_id}",
        headers={**headers, "If-Match": "3"},
        json={"water_source_id": source_id},
    )
    assert linked.status_code == 200, linked.text
    assert linked.json()["water_source"]["id"] == source_id
    removed = client.delete(f"/v1/water-sources/{source_id}", headers=headers)
    assert removed.status_code == 204
    station = client.get(f"/v1/farms/{farm.id}/station", headers=headers)
    assert station.status_code == 200
    pump = station.json()["pumps"][0]
    assert pump["water_source"] is None
    assert pump["serves_all_blocks"] is False
    assert len(pump["windows"]) == 2


def test_capacity_check_with_a_40_m3h_block_and_a_30_m3h_pump(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm, headers = _owner(make_user, make_farm, auth_header, "capacity@agrect.app")
    done = _complete_block(
        client,
        farm,
        headers,
        name="North",
        rows_total=2,
        flow_m3h="40",
        valves=[
            {"name": "V1", "row_from": 1, "row_to": 1},
            {"name": "V2", "row_from": 2, "row_to": 2},
        ],
    )
    block_id = str(done["id"])
    flows = sorted(Decimal(valve["q_m3h"]) for valve in done["valves"])
    assert flows == [Decimal("20"), Decimal("20")]
    draft = client.post(
        f"/v1/farms/{farm.id}/blocks",
        headers=headers,
        json={"name": "Draft", "rows_total": 1, "net_area_ha": "1"},
    )
    assert draft.status_code == 201
    laid = _put(
        client,
        f"/v1/blocks/{draft.json()['id']}/irrigation-layout",
        headers,
        int(draft.json()["version"]),
        {
            "system": "drip",
            "entry_mode": "typed_flow",
            "typed_flow_basis": "block",
            "typed_flow_m3h": "100",
        },
    )
    assert laid.status_code == 200, laid.text
    pump = client.post(
        f"/v1/farms/{farm.id}/station/pumps",
        headers=headers,
        json={"name": "P1", "flow_m3h": "30"},
    )
    assert pump.status_code == 201, pump.text

    checked = client.get(
        f"/v1/farms/{farm.id}/capacity-check",
        headers=headers,
        params={"mode": "today"},
    )
    assert checked.status_code == 200, checked.text
    body = checked.json()
    assert body["mode"] == "today"
    assert body["source"] == "calculated"
    summary = body["summary"]
    assert Decimal(summary["open_together_flow_m3h"]) == Decimal("40")
    assert Decimal(summary["pumps_flow_m3h"]) == Decimal("30")
    assert Decimal(summary["short_by_m3h"]) == Decimal("10")
    assert len(body["shifts"]) == 2
    assert body["cannot_supply"] == []
    assert {Decimal(shift["flow_m3h"]) for shift in body["shifts"]} == {Decimal("20")}
    assert block_id in body["no_dose_blocks"]
    assert summary["hours_available"] is None
    assert summary["fits_in_hours"] is None


def test_today_uses_the_recommended_run_time(
    client: TestClient,
    db: Session,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm, headers = _owner(make_user, make_farm, auth_header, "today-dose@agrect.app")
    done = _complete_block(
        client,
        farm,
        headers,
        name="North",
        rows_total=1,
        flow_m3h="10",
    )
    block_id = str(done["id"])
    rate = Decimal(str(done["rate_mm_h"]))
    _weather(db, farm, _today(), "5", forecast=True)
    db.commit()
    load_catalog()
    texture = db.scalar(select(SoilTextureClass).where(SoilTextureClass.code == "loam"))
    assert texture is not None
    soil = client.put(
        f"/v1/blocks/{block_id}/soil",
        headers=headers,
        json={
            "texture_mode": "class",
            "texture_class_id": str(texture.id),
            "root_depth_m": "1.0",
            "dry_down_pct": "50",
            "full_on": _today().isoformat(),
        },
    )
    assert soil.status_code == 200, soil.text
    settings = client.put(
        f"/v1/blocks/{block_id}/irrigation-settings",
        headers=headers,
        json={"efficiency": "1", "kc": "1", "kc_source": "entered"},
    )
    assert settings.status_code == 200, settings.text
    pump = client.post(
        f"/v1/farms/{farm.id}/station/pumps",
        headers=headers,
        json={"name": "P1", "flow_m3h": "20"},
    )
    assert pump.status_code == 201, pump.text
    window = client.put(
        f"/v1/pumps/{pump.json()['id']}/windows",
        headers={**headers, "If-Match": pump.headers["etag"]},
        json={"windows": [{"start_time": "22:00", "end_time": "06:00"}]},
    )
    assert window.status_code == 200, window.text

    checked = client.get(
        f"/v1/farms/{farm.id}/capacity-check",
        headers=headers,
        params={"mode": "today"},
    )
    assert checked.status_code == 200, checked.text
    body = checked.json()
    expected_min = soil_calc.run_time_min(
        soil_calc.gross_mm(soil_calc.etc_mm(Decimal("5"), Decimal("1")), Decimal("1")),
        rate,
    )
    assert body["no_dose_blocks"] == []
    assert len(body["shifts"]) == 1
    assert Decimal(body["shifts"][0]["time_min"]) == expected_min
    assert Decimal(body["summary"]["hours_needed"]) == expected_min / Decimal("60")
    assert Decimal(body["summary"]["hours_available"]) == Decimal("8")
    assert body["summary"]["fits_in_hours"] is True
    assert Decimal(body["summary"]["short_by_m3h"]) == Decimal("0")
    assert body["source"] == "calculated"


def test_peak_week_uses_the_largest_gross_need_in_the_fortnight(
    client: TestClient,
    db: Session,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm, headers = _owner(make_user, make_farm, auth_header, "peak@agrect.app")
    done = _complete_block(
        client,
        farm,
        headers,
        name="North",
        rows_total=1,
        flow_m3h="10",
    )
    block_id = str(done["id"])
    rate = Decimal(str(done["rate_mm_h"]))
    today = _today()
    _weather(db, farm, today - timedelta(days=7), "100", forecast=False)
    _weather(db, farm, today - timedelta(days=6), "2", forecast=False)
    _weather(db, farm, today, "3", forecast=False)
    _weather(db, farm, today + timedelta(days=6), "5", forecast=True)
    _weather(db, farm, today + timedelta(days=7), "100", forecast=True)
    db.commit()
    settings = client.put(
        f"/v1/blocks/{block_id}/irrigation-settings",
        headers=headers,
        json={"efficiency": "1", "kc": "1", "kc_source": "entered"},
    )
    assert settings.status_code == 200, settings.text
    pump = client.post(
        f"/v1/farms/{farm.id}/station/pumps",
        headers=headers,
        json={"name": "P1", "flow_m3h": "50"},
    )
    assert pump.status_code == 201, pump.text

    checked = client.get(
        f"/v1/farms/{farm.id}/capacity-check",
        headers=headers,
        params={"mode": "peak_week"},
    )
    assert checked.status_code == 200, checked.text
    body = checked.json()
    expected_min = soil_calc.run_time_min(
        soil_calc.gross_mm(soil_calc.etc_mm(Decimal("5"), Decimal("1")), Decimal("1")),
        rate,
    )
    assert body["mode"] == "peak_week"
    assert body["source"] == "calculated"
    assert body["no_dose_blocks"] == []
    assert Decimal(body["shifts"][0]["time_min"]) == expected_min
    assert Decimal(body["summary"]["hours_needed"]) == expected_min / Decimal("60")

    bare = _complete_block(
        client,
        farm,
        headers,
        name="Bare",
        rows_total=1,
        flow_m3h="10",
    )
    again = client.get(
        f"/v1/farms/{farm.id}/capacity-check",
        headers=headers,
        params={"mode": "peak_week"},
    )
    assert again.status_code == 200
    assert str(bare["id"]) in again.json()["no_dose_blocks"]
    assert block_id not in again.json()["no_dose_blocks"]


def test_capacity_decision_requires_a_reason_and_does_not_irrigate(
    client: TestClient,
    db: Session,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm, headers = _owner(make_user, make_farm, auth_header, "decision@agrect.app")
    block = client.post(
        f"/v1/farms/{farm.id}/blocks",
        headers=headers,
        json={"name": "North"},
    )
    assert block.status_code == 201
    blank = client.post(
        f"/v1/farms/{farm.id}/capacity-decisions",
        headers=headers,
        json={"choice": "share", "reason": "   "},
    )
    assert blank.status_code == 422
    assert blank.json()["fields"]["reason"] == "record.reason_required"
    saved = client.post(
        f"/v1/farms/{farm.id}/capacity-decisions",
        headers=headers,
        json={
            "choice": "priority",
            "reason": "North first",
            "block_ids": [block.json()["id"]],
            "mode": "today",
        },
    )
    assert saved.status_code == 201, saved.text
    body = saved.json()
    assert body["choice"] == "priority"
    assert body["reason"] == "North first"
    assert body["mode"] == "today"
    assert body["snapshot"]["source"] == "calculated"
    assert body["block_ids"] == [block.json()["id"]]
    row = db.scalar(select(CapacityDecision).where(CapacityDecision.farm_id == farm.id))
    assert row is not None
    assert row.reason == "North first"
    assert row.choice.value == "priority"
    events = db.scalar(
        select(func.count()).select_from(IrrigationEvent).where(IrrigationEvent.farm_id == farm.id)
    )
    assert events == 0


def test_another_farm_pump_and_blocks_are_not_found(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm, headers = _owner(make_user, make_farm, auth_header, "scope-a@agrect.app")
    created = client.post(
        f"/v1/farms/{farm.id}/station/pumps",
        headers=headers,
        json={"name": "P1", "flow_m3h": "12"},
    )
    assert created.status_code == 201, created.text
    pump_id = created.json()["id"]
    source = client.post(
        f"/v1/farms/{farm.id}/water-sources",
        headers=headers,
        json={"name": "Net", "kind": "network"},
    )
    assert source.status_code == 201
    outsider = make_user("scope-b@agrect.app", "station-password")
    headers_b = auth_header(outsider)
    denied = (
        client.patch(
            f"/v1/pumps/{pump_id}",
            headers={**headers_b, "If-Match": "1"},
            json={"name": "Stolen"},
        ),
        client.put(
            f"/v1/pumps/{pump_id}/windows",
            headers={**headers_b, "If-Match": "1"},
            json={"windows": []},
        ),
        client.put(
            f"/v1/pumps/{pump_id}/blocks",
            headers={**headers_b, "If-Match": "1"},
            json={"block_ids": []},
        ),
        client.delete(f"/v1/pumps/{pump_id}", headers={**headers_b, "If-Match": "1"}),
    )
    for response in denied:
        assert response.status_code == 404
        assert response.json() == {"code": "pump.not_found"}
    station = client.get(f"/v1/farms/{farm.id}/station", headers=headers_b)
    assert station.status_code == 404
    assert station.json() == {"code": "farm.not_found"}
    foreign_source = client.patch(
        f"/v1/water-sources/{source.json()['id']}",
        headers=headers_b,
        json={"name": "Stolen"},
    )
    assert foreign_source.status_code == 404
    assert foreign_source.json() == {"code": "water_source.not_found"}
    missing = client.patch(
        f"/v1/pumps/{uuid.uuid4()}",
        headers={**headers, "If-Match": "1"},
        json={"name": "Gone"},
    )
    assert missing.status_code == 404
    assert missing.json() == {"code": "pump.not_found"}
