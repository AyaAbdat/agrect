"""Season timeline in one request; machine list details; fixed query counts."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from sqlalchemy import event, select
from sqlalchemy.orm import Session

from app.core.db import engine
from app.modules.auth.models import AppUser
from app.modules.catalog.models import Crop, StageDef
from app.modules.farms.models import Farm
from app.modules.harvest.models import HarvestBasis, HarvestEntry, HarvestUnit
from app.modules.phenology.models import BlockSeason, StageObservation
from app.modules.soilwater.models import IrrigationEvent, IrrigationSource
from tests.test_operations_api import _ops_block, _owner, _valve_ids
from tests.vectors import D

ZONE = ZoneInfo("Africa/Algiers")


@contextmanager
def _count_queries() -> Iterator[list[str]]:
    seen: list[str] = []

    def before(_conn, _cursor, statement, _params, _context, _many) -> None:  # noqa: ANN001
        seen.append(statement)

    event.listen(engine, "before_cursor_execute", before)
    try:
        yield seen
    finally:
        event.remove(engine, "before_cursor_execute", before)


def _season(db: Session, farm: Farm, block_id: str, start: date) -> BlockSeason:
    season = BlockSeason(farm_id=farm.id, block_id=block_id, year=start.year, start_date=start)
    db.add(season)
    db.flush()
    return season


def _observe(db: Session, farm: Farm, user: AppUser, season: BlockSeason, code: str, on: date):
    crop_id = db.scalar(select(Crop.id).where(Crop.code == "table_grape"))
    stage = db.scalar(select(StageDef).where(StageDef.crop_id == crop_id, StageDef.code == code))
    assert stage is not None, code
    db.add(
        StageObservation(
            farm_id=farm.id,
            block_season_id=season.id,
            stage_def_id=stage.id,
            observed_on=on,
            user_id=user.id,
        )
    )
    return stage


def _harvest(
    db: Session, farm: Farm, user: AppUser, block_id: str, on: date, pass_no: int, kg: str
):
    db.add(
        HarvestEntry(
            farm_id=farm.id,
            block_id=block_id,
            date=on,
            pass_no=pass_no,
            quantity=Decimal(kg),
            unit=HarvestUnit.kg,
            basis=HarvestBasis.block,
            kg=Decimal(kg),
            kg_ha=Decimal(kg) / Decimal("1.5"),
            area_ha=Decimal("1.5"),
            inputs_hash="0" * 64,
            user_id=user.id,
        )
    )


def _irrigate(db: Session, farm: Farm, user: AppUser, block_id: str, valve: str, on: date) -> None:
    db.add(
        IrrigationEvent(
            farm_id=farm.id,
            block_id=block_id,
            valve_ids=[valve],
            start_at=datetime.combine(on, time(6), tzinfo=ZONE).astimezone(UTC),
            duration_min=60,
            depth_mm=Decimal("5"),
            volume_m3=Decimal("10"),
            soil_mm=Decimal("5"),
            runoff_mm=Decimal("0"),
            source=IrrigationSource.calculated,
            entered_by=user.id,
        )
    )


def _stage_codes(db: Session) -> list[str]:
    crop_id = db.scalar(select(Crop.id).where(Crop.code == "table_grape"))
    return list(
        db.scalars(select(StageDef.code).where(StageDef.crop_id == crop_id).order_by(StageDef.sort))
    )


def test_timeline_two_blocks(
    client: TestClient,
    db: Session,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm, headers, user = _owner(make_user, make_farm, auth_header, "timeline@agrect.app")
    north = str(_ops_block(client, farm, headers, name="North")["id"])
    south = str(_ops_block(client, farm, headers, name="South")["id"])
    codes = _stage_codes(db)

    season = _season(db, farm, north, date(2026, 3, 1))
    first = _observe(db, farm, user, season, codes[0], date(2026, 3, 20))
    _observe(db, farm, user, season, codes[1], date(2026, 4, 15))
    _observe(db, farm, user, season, codes[2], date(2025, 4, 1))  # outside the range
    _harvest(db, farm, user, north, date(2026, 8, 20), 2, "900")
    _harvest(db, farm, user, north, date(2026, 8, 10), 1, "1200.5")
    valve = _valve_ids(db, north)[0]
    # Wed 3 Jun and Sun 7 Jun -> week of Mon 1 Jun; Mon 8 Jun -> next week.
    for day in (date(2026, 6, 3), date(2026, 6, 7), date(2026, 6, 8)):
        _irrigate(db, farm, user, north, valve, day)
    db.commit()

    product = client.post(
        f"/v1/farms/{farm.id}/products",
        headers=headers,
        json={"name": "Copper", "kind": "crop_protection", "unit": "l"},
    ).json()
    spray = client.post(
        f"/v1/farms/{farm.id}/operations",
        headers=headers,
        json={
            "block_id": south,
            "type": "crop_protection_spray",
            "date": "2026-05-02",
            "products": [
                {
                    "product_id": product["id"],
                    "rate": "1",
                    "rate_unit": "l",
                    "rate_basis": "per_block",
                }
            ],
        },
    )
    assert spray.status_code == 201, spray.text

    response = client.get(
        f"/v1/farms/{farm.id}/timeline",
        headers=headers,
        params={"from": "2026-01-01", "to": "2026-12-31"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["date_from"] == "2026-01-01"
    assert body["date_to"] == "2026-12-31"
    rows = {row["block"]["name"]: row for row in body["blocks"]}
    assert list(rows) == ["North", "South"]

    n = rows["North"]
    assert n["crop"]["code"] == "table_grape"
    assert set(n["crop"]["names"]) == {"fr", "ar", "en"}
    assert n["season_start"] == "2026-03-01"
    assert [stage["date"] for stage in n["stages"]] == ["2026-03-20", "2026-04-15"]
    assert n["stages"][0]["code"] == first.code
    assert n["stages"][0]["names"]["en"] == first.name_en
    assert [(h["date"], h["pass_no"]) for h in n["harvest"]] == [
        ("2026-08-10", 1),
        ("2026-08-20", 2),
    ]
    assert D(n["harvest"][0]["kg"]) == D("1200.5")
    assert n["first_harvest_date"] == "2026-08-10"
    assert n["operations"] == []
    assert n["irrigation_weeks"] == [
        {"week_start": "2026-06-01", "count": 2},
        {"week_start": "2026-06-08", "count": 1},
    ]

    s = rows["South"]
    assert s["season_start"] is None
    assert s["first_harvest_date"] is None
    assert s["stages"] == []
    assert s["harvest"] == []
    assert s["irrigation_weeks"] == []
    assert s["operations"] == [
        {"date": "2026-05-02", "type": "crop_protection_spray", "products": ["Copper"]}
    ]


def test_timeline_query_count_does_not_grow_with_blocks(
    client: TestClient,
    db: Session,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm, headers, user = _owner(make_user, make_farm, auth_header, "timeline-q@agrect.app")

    def measure() -> int:
        with _count_queries() as seen:
            response = client.get(f"/v1/farms/{farm.id}/timeline", headers=headers)
        assert response.status_code == 200, response.text
        return len(seen)

    def add_block(name: str) -> None:
        block_id = str(_ops_block(client, farm, headers, name=name)["id"])
        season = _season(db, farm, block_id, date(datetime.now(ZONE).year, 3, 1))
        _observe(db, farm, user, season, _stage_codes(db)[0], season.start_date)
        _harvest(db, farm, user, block_id, season.start_date + timedelta(days=100), 1, "10")
        db.commit()

    add_block("A")
    one = measure()
    add_block("B")
    add_block("C")
    three = measure()
    assert one == three


def test_timeline_default_range_errors_and_scoping(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm, headers, _user = _owner(make_user, make_farm, auth_header, "timeline-r@agrect.app")
    _other, other_headers, _ = _owner(make_user, make_farm, auth_header, "timeline-o@agrect.app")
    year = datetime.now(ZONE).year

    default = client.get(f"/v1/farms/{farm.id}/timeline", headers=headers)
    assert default.status_code == 200
    assert default.json()["date_from"] == f"{year}-01-01"
    assert default.json()["date_to"] == f"{year}-12-31"
    assert default.json()["blocks"] == []

    # 731 days is allowed (two years including a leap day); 732 is not.
    allowed = client.get(
        f"/v1/farms/{farm.id}/timeline",
        headers=headers,
        params={"from": "2027-01-01", "to": "2028-12-31"},
    )
    assert allowed.status_code == 200, allowed.text
    too_long = client.get(
        f"/v1/farms/{farm.id}/timeline",
        headers=headers,
        params={"from": "2026-12-31", "to": "2028-12-31"},
    )
    assert too_long.status_code == 422
    assert too_long.json()["fields"] == {"to": "timeline.range_too_long"}
    backwards = client.get(
        f"/v1/farms/{farm.id}/timeline",
        headers=headers,
        params={"from": "2026-06-01", "to": "2026-05-01"},
    )
    assert backwards.status_code == 422
    assert backwards.json()["fields"] == {"to": "timeline.range_invalid"}

    hidden = client.get(f"/v1/farms/{farm.id}/timeline", headers=other_headers)
    assert hidden.status_code == 404


def test_machine_list_details_without_per_row_queries(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    farm, headers, _user = _owner(make_user, make_farm, auth_header, "machines-q@agrect.app")
    block_id = str(_ops_block(client, farm, headers)["id"])

    def add_machine(name: str) -> str:
        machine = client.post(
            f"/v1/farms/{farm.id}/machines",
            headers=headers,
            json={
                "type": "tractor",
                "name": name,
                "engine_hours_reading": "1000",
                "reading_date": "2026-03-01",
            },
        ).json()
        task = client.post(
            f"/v1/machines/{machine['id']}/maintenance",
            headers=headers,
            json={"task": "Oil", "interval_h": "250", "last_done_h": "800"},
        )
        assert task.status_code == 201, task.text
        used = client.post(
            f"/v1/farms/{farm.id}/operations",
            headers=headers,
            json={
                "block_id": block_id,
                "type": "tillage",
                "date": "2026-03-10",
                "machines": [{"machine_id": machine["id"], "hours": "2"}],
            },
        )
        assert used.status_code == 201, used.text
        return str(machine["id"])

    def measure() -> tuple[int, list[dict[str, object]]]:
        with _count_queries() as seen:
            response = client.get(f"/v1/farms/{farm.id}/machines", headers=headers)
        assert response.status_code == 200, response.text
        return len(seen), response.json()["machines"]

    first_id = add_machine("T1")
    one, machines = measure()
    item = machines[0]
    # Existing fields are kept; the row details are added.
    for field in ("id", "farm_id", "type", "name", "status", "engine_hours_reading", "version"):
        assert field in item
    assert D(str(item["current_engine_hours"])) == D("1002")
    assert item["current_engine_hours_source"] == "calculated"
    assert len(item["maintenance"]) == 1
    assert D(str(item["maintenance"][0]["due"]["next_due_h"])) == D("1050")
    assert item["maintenance"][0]["due"]["due_by_hours"] is False

    detail = client.get(f"/v1/machines/{first_id}", headers=headers).json()
    assert item["current_engine_hours"] == detail["current_engine_hours"]
    assert item["maintenance"] == detail["maintenance"]

    add_machine("T2")
    add_machine("T3")
    three, machines = measure()
    assert len(machines) == 3
    assert one == three
