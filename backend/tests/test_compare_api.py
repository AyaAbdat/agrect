"""Compare endpoint: one metric across complete blocks, mean_7d, drift flag, scoping."""

from collections.abc import Callable
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.modules.auth.models import AppUser
from app.modules.farms.models import Farm
from app.modules.soilwater.models import (
    IrrigationEvent,
    IrrigationSettings,
    IrrigationSource,
    WaterBalanceDaily,
    WbStatus,
)
from tests.test_operations_api import _ops_block, _owner, _valve_ids
from tests.vectors import D

ON = date(2026, 6, 10)
ZONE = ZoneInfo("Africa/Algiers")


def _balance(
    db: Session,
    farm: Farm,
    block_id: str,
    day: date,
    *,
    depletion: str,
    etc: str,
    taw: str = "100",
) -> None:
    db.add(
        WaterBalanceDaily(
            block_id=block_id,
            date=day,
            farm_id=farm.id,
            et0_mm=Decimal("5"),
            kc=Decimal("0.8"),
            etc_mm=Decimal(etc),
            rain_mm=Decimal("0"),
            irrigation_soil_mm=Decimal("0"),
            runoff_mm=Decimal("0"),
            drainage_mm=Decimal("0"),
            depletion_mm=Decimal(depletion),
            taw_mm=Decimal(taw),
            raw_mm=Decimal("50"),
            status=WbStatus.ok,
            is_forecast=False,
            inputs_hash="0" * 64,
        )
    )


def _settings(db: Session, farm: Farm, block_id: str, kc: str, efficiency: str) -> None:
    db.add(
        IrrigationSettings(
            farm_id=farm.id,
            block_id=block_id,
            kc=Decimal(kc),
            efficiency=Decimal(efficiency),
        )
    )


def _two_blocks(client: TestClient, farm: Farm, headers: dict[str, str]) -> tuple[str, str]:
    north = str(_ops_block(client, farm, headers, name="North")["id"])
    south = str(_ops_block(client, farm, headers, name="South")["id"])
    return north, south


def _week(db: Session, farm: Farm, block_id: str, depletions: list[str], etcs: list[str]) -> None:
    for offset, (depletion, etc) in enumerate(zip(depletions, etcs, strict=True)):
        _balance(db, farm, block_id, ON - timedelta(days=6 - offset), depletion=depletion, etc=etc)


def test_compare_water_values_and_mean_7d(
    client: TestClient,
    db: Session,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm, headers, user = _owner(make_user, make_farm, auth_header, "compare-water@agrect.app")
    north, south = _two_blocks(client, farm, headers)
    # North: water left 100-10 .. 100-70 -> mean 60, on the date 30; ETc 1..7 -> mean 4.
    _week(
        db,
        farm,
        north,
        ["10", "20", "30", "40", "50", "60", "70"],
        ["1", "2", "3", "4", "5", "6", "7"],
    )
    # South: only two days stored -> mean over the stored days.
    _balance(db, farm, south, ON - timedelta(days=1), depletion="40", etc="3")
    _balance(db, farm, south, ON, depletion="20", etc="5")
    # Outside the window: ignored.
    _balance(db, farm, south, ON - timedelta(days=9), depletion="0", etc="99")
    for block_id in (north, south):
        _settings(db, farm, block_id, "0.80", "0.900")
    db.commit()

    left = client.get(
        f"/v1/farms/{farm.id}/compare",
        headers=headers,
        params={"metric": "water_left", "date": ON.isoformat()},
    )
    assert left.status_code == 200, left.text
    body = left.json()
    assert body["available"] is True
    assert body["date"] == ON.isoformat()
    rows = {row["block"]["name"]: row for row in body["rows"]}
    assert D(rows["North"]["value"]) == D("30")
    assert D(rows["North"]["mean_7d"]) == D("60")
    assert rows["North"]["unit"] == "mm"
    assert rows["North"]["source"] == "calculated"
    assert D(rows["South"]["value"]) == D("80")
    assert D(rows["South"]["mean_7d"]) == D("70")

    use = client.get(
        f"/v1/farms/{farm.id}/compare",
        headers=headers,
        params={"metric": "crop_water_use", "date": ON.isoformat()},
    ).json()
    rows = {row["block"]["name"]: row for row in use["rows"]}
    assert D(rows["North"]["value"]) == D("7")
    assert D(rows["North"]["mean_7d"]) == D("4")
    assert D(rows["South"]["value"]) == D("5")
    assert D(rows["South"]["mean_7d"]) == D("4")


def test_compare_water_applied(
    client: TestClient,
    db: Session,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm, headers, user = _owner(make_user, make_farm, auth_header, "compare-applied@agrect.app")
    north, south = _two_blocks(client, farm, headers)
    valve = _valve_ids(db, north)[0]

    def event(block_id: str, day: date, depth: str) -> None:
        db.add(
            IrrigationEvent(
                farm_id=farm.id,
                block_id=block_id,
                valve_ids=[valve],
                start_at=datetime.combine(day, time(23, 30), tzinfo=ZONE).astimezone(UTC),
                duration_min=60,
                depth_mm=Decimal(depth),
                volume_m3=Decimal("10"),
                soil_mm=Decimal(depth),
                runoff_mm=Decimal("0"),
                source=IrrigationSource.calculated,
                entered_by=user.id,
            )
        )

    # 23:30 farm-local is the previous UTC day: the farm-local date counts.
    event(north, ON, "8")
    event(north, ON, "4")
    event(north, ON - timedelta(days=3), "9")
    event(north, ON - timedelta(days=8), "50")
    db.commit()

    body = client.get(
        f"/v1/farms/{farm.id}/compare",
        headers=headers,
        params={"metric": "water_applied", "date": ON.isoformat()},
    ).json()
    rows = {row["block"]["name"]: row for row in body["rows"]}
    assert D(rows["North"]["value"]) == D("12")
    assert D(rows["North"]["mean_7d"]) == D("3")
    assert D(rows["South"]["value"]) == D("0")
    assert D(rows["South"]["mean_7d"]) == D("0")
    assert rows["South"]["source"] == "calculated"


def test_compare_drift_flag_same_setting(
    client: TestClient,
    db: Session,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm, headers, _user = _owner(make_user, make_farm, auth_header, "compare-drift@agrect.app")
    north, south = _two_blocks(client, farm, headers)
    east = str(_ops_block(client, farm, headers, name="East")["id"])
    # Same crop, Kc and efficiency. Water left 80, 75, 20; TAW 100 -> median 75.
    # East is 55 mm from the median (> 25 mm); North (5 mm) is not.
    _balance(db, farm, north, ON, depletion="20", etc="5")
    _balance(db, farm, south, ON, depletion="25", etc="5")
    _balance(db, farm, east, ON, depletion="80", etc="5")
    for block_id in (north, south, east):
        _settings(db, farm, block_id, "0.80", "0.900")
    db.commit()

    body = client.get(
        f"/v1/farms/{farm.id}/compare",
        headers=headers,
        params={"metric": "water_left", "date": ON.isoformat()},
    ).json()
    assert body["flags"] == [
        {
            "block_ids": [east],
            "metric": "water_left",
            "message_code": "compare.drift_same_setting",
        }
    ]

    # A different efficiency on East puts it in its own group: no flag.
    setting = db.query(IrrigationSettings).filter(IrrigationSettings.block_id == east).one()
    setting.efficiency = Decimal("0.850")
    db.commit()
    body = client.get(
        f"/v1/farms/{farm.id}/compare",
        headers=headers,
        params={"metric": "water_left", "date": ON.isoformat()},
    ).json()
    assert body["flags"] == []


def test_compare_degree_days_stage_and_unavailable(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm, headers, _user = _owner(make_user, make_farm, auth_header, "compare-misc@agrect.app")
    _two_blocks(client, farm, headers)
    for metric in ("degree_days", "stage"):
        body = client.get(
            f"/v1/farms/{farm.id}/compare",
            headers=headers,
            params={"metric": metric, "date": ON.isoformat()},
        ).json()
        assert [row["block"]["name"] for row in body["rows"]] == ["North", "South"]
        # No degree-day setting and no season: values are null, never invented.
        assert all(row["value"] is None and row["mean_7d"] is None for row in body["rows"])

    pests = client.get(
        f"/v1/farms/{farm.id}/compare", headers=headers, params={"metric": "pest_count"}
    )
    assert pests.status_code == 200
    assert pests.json()["available"] is False
    assert pests.json()["unavailable_code"] == "compare.metric_unavailable"
    assert pests.json()["rows"] == []

    yesterday = (datetime.now(ZONE).date() - timedelta(days=1)).isoformat()
    default = client.get(
        f"/v1/farms/{farm.id}/compare", headers=headers, params={"metric": "water_left"}
    )
    assert default.json()["date"] == yesterday

    bad = client.get(f"/v1/farms/{farm.id}/compare", headers=headers, params={"metric": "nope"})
    assert bad.status_code == 422


def test_compare_scoping_404(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm_a, _headers_a, _ = _owner(make_user, make_farm, auth_header, "compare-a@agrect.app")
    _farm_b, headers_b, _ = _owner(make_user, make_farm, auth_header, "compare-b@agrect.app")
    hidden = client.get(
        f"/v1/farms/{farm_a.id}/compare", headers=headers_b, params={"metric": "water_left"}
    )
    assert hidden.status_code == 404
