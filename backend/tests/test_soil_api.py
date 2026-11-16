import uuid
from collections.abc import Callable
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.auth.models import AppUser
from app.modules.catalog.loader import load_catalog
from app.modules.catalog.models import SoilTextureClass
from app.modules.farms.models import Farm
from app.modules.registry.models import RecordVersion
from app.modules.soilwater.models import SoilProfile


@pytest.fixture
def _catalog() -> None:
    load_catalog()


def _owner(
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
    email: str = "soil@agrect.app",
) -> tuple[AppUser, Farm, dict[str, str]]:
    user = make_user(email, "soil-password")
    farm = make_farm(user, "Farm", Decimal("36"), Decimal("3"))
    return user, farm, auth_header(user)


def _block_id(client: TestClient, farm: Farm, headers: dict[str, str], name: str = "North") -> str:
    created = client.post(f"/v1/farms/{farm.id}/blocks", headers=headers, json={"name": name})
    assert created.status_code == 201
    block_id = created.json()["id"]
    assert isinstance(block_id, str)
    return block_id


def _texture_id(db: Session, code: str) -> str:
    row = db.scalar(select(SoilTextureClass).where(SoilTextureClass.code == code))
    assert row is not None
    return str(row.id)


def test_empty_soil_and_settings_are_null(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    _user, farm, headers = _owner(make_user, make_farm, auth_header)
    block_id = _block_id(client, farm, headers)
    soil = client.get(f"/v1/blocks/{block_id}/soil", headers=headers)
    assert soil.status_code == 200
    body = soil.json()
    assert body["texture_mode"] is None
    assert body["texture_class"] is None
    assert body["theta_fc"] is None
    assert body["theta_wp"] is None
    assert body["taw_mm"] is None
    assert body["raw_mm"] is None
    assert body["water_left_mm"] is None
    assert body["irrigate_below_mm"] is None
    assert body["version"] is None
    assert body["label"] == "not_enough_data"
    settings = client.get(f"/v1/blocks/{block_id}/irrigation-settings", headers=headers)
    assert settings.status_code == 200
    assert settings.json() == {
        "efficiency": None,
        "kc": None,
        "kc_source": None,
        "version": None,
    }


@pytest.mark.usefixtures("_catalog")
def test_loam_profile_computes_taw_and_raw(
    client: TestClient,
    db: Session,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    user, farm, headers = _owner(make_user, make_farm, auth_header)
    block_id = _block_id(client, farm, headers)
    saved = client.put(
        f"/v1/blocks/{block_id}/soil",
        headers=headers,
        json={
            "texture_mode": "class",
            "texture_class_id": _texture_id(db, "loam"),
            "root_depth_m": "1.0",
            "dry_down_pct": "50",
            "full_on": "2026-11-01",
            "organic_matter_pct": "1.5",
            "compaction": "normal",
            "infiltration_mm_h": "8",
            "infiltration_source": "ring_test",
        },
    )
    assert saved.status_code == 200
    assert saved.headers["etag"] == "1"
    body = saved.json()
    assert body["texture_mode"] == "class"
    assert body["texture_class"]["code"] == "loam"
    assert set(body["texture_class"]["name"]) == {"fr", "ar", "en"}
    assert body["theta_fc"] == "0.250"
    assert body["theta_wp"] == "0.120"
    assert Decimal(body["root_depth_m"]) == Decimal("1.0")
    assert Decimal(body["dry_down_pct"]) == Decimal("50")
    assert Decimal(body["taw_mm"]) == Decimal("130.0")
    assert Decimal(body["raw_mm"]) == Decimal("65.0")
    assert body["label"] == "calculated"
    assert body["full_on"] == "2026-11-01"
    assert Decimal(body["organic_matter_pct"]) == Decimal("1.5")
    assert body["compaction"] == "normal"
    assert Decimal(body["infiltration_mm_h"]) == Decimal("8")
    assert body["infiltration_source"] == "ring_test"
    assert body["sources"]["theta"] == "calculated"
    assert body["sources"]["taw"] == "calculated"
    assert body["sources"]["root_depth_m"] == "entered"
    assert body["sources"]["infiltration_mm_h"] == "measured"
    assert body["version"] == 1
    db.expire_all()
    assert (
        db.scalar(select(RecordVersion).where(RecordVersion.entity_type == "soil_profile")) is None
    )

    missing = client.put(
        f"/v1/blocks/{block_id}/soil",
        headers=headers,
        json={"texture_mode": "class", "texture_class_id": _texture_id(db, "loam")},
    )
    assert missing.status_code == 428
    assert missing.json() == {"code": "conflict.version_required"}
    stale = client.put(
        f"/v1/blocks/{block_id}/soil",
        headers={**headers, "If-Match": "0"},
        json={
            "texture_mode": "class",
            "texture_class_id": _texture_id(db, "loam"),
            "root_depth_m": "1.0",
            "dry_down_pct": "40",
        },
    )
    assert stale.status_code == 409
    assert stale.json() == {"code": "conflict.version"}
    blank = client.put(
        f"/v1/blocks/{block_id}/soil",
        headers={**headers, "If-Match": "1"},
        json={
            "texture_mode": "class",
            "texture_class_id": _texture_id(db, "loam"),
            "root_depth_m": "1.0",
            "dry_down_pct": "40",
            "reason": "  ",
        },
    )
    assert blank.status_code == 422
    assert blank.json()["fields"]["reason"] == "record.reason_required"
    updated = client.put(
        f"/v1/blocks/{block_id}/soil",
        headers={**headers, "If-Match": "1"},
        json={
            "texture_mode": "class",
            "texture_class_id": _texture_id(db, "loam"),
            "root_depth_m": "1.0",
            "dry_down_pct": "40",
            "full_on": "2026-11-01",
            "organic_matter_pct": "1.5",
            "compaction": "normal",
            "infiltration_mm_h": "8",
            "infiltration_source": "ring_test",
            "reason": "lower dry down",
        },
    )
    assert updated.status_code == 200
    assert updated.headers["etag"] == "2"
    assert updated.json()["version"] == 2
    assert Decimal(updated.json()["raw_mm"]) == Decimal("52")
    again = client.put(
        f"/v1/blocks/{block_id}/soil",
        headers={**headers, "If-Match": "1"},
        json={
            "texture_mode": "class",
            "texture_class_id": _texture_id(db, "loam"),
            "root_depth_m": "1.2",
            "dry_down_pct": "40",
        },
    )
    assert again.status_code == 409
    db.expire_all()
    history = db.scalars(
        select(RecordVersion)
        .where(RecordVersion.entity_type == "soil_profile")
        .order_by(RecordVersion.version)
    ).all()
    profile = db.scalar(select(SoilProfile).where(SoilProfile.block_id == uuid.UUID(block_id)))
    assert profile is not None
    assert len(history) == 1
    assert history[0].version == 2
    assert history[0].entity_id == profile.id
    assert history[0].changed_fields == ["dry_down_pct"]
    assert history[0].reason == "lower dry down"
    assert history[0].user_id == user.id


@pytest.mark.usefixtures("_catalog")
def test_clay_loam_has_no_theta(
    client: TestClient,
    db: Session,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    _user, farm, headers = _owner(make_user, make_farm, auth_header, "clay@agrect.app")
    block_id = _block_id(client, farm, headers)
    saved = client.put(
        f"/v1/blocks/{block_id}/soil",
        headers=headers,
        json={
            "texture_mode": "class",
            "texture_class_id": _texture_id(db, "clay_loam"),
            "root_depth_m": "1.0",
            "dry_down_pct": "50",
        },
    )
    assert saved.status_code == 200
    body = saved.json()
    assert body["texture_class"]["code"] == "clay_loam"
    assert body["theta_fc"] is None
    assert body["theta_wp"] is None
    assert body["taw_mm"] is None
    assert body["raw_mm"] is None
    assert body["label"] == "not_enough_data"


def test_percent_mode_stores_fractions_without_theta(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    _user, farm, headers = _owner(make_user, make_farm, auth_header, "percent@agrect.app")
    block_id = _block_id(client, farm, headers)
    saved = client.put(
        f"/v1/blocks/{block_id}/soil",
        headers=headers,
        json={
            "texture_mode": "percent",
            "sand_pct": "40",
            "silt_pct": "40",
            "clay_pct": "20",
            "root_depth_m": "1.0",
            "dry_down_pct": "50",
        },
    )
    assert saved.status_code == 200
    body = saved.json()
    assert body["texture_mode"] == "percent"
    assert body["texture_class"] is None
    assert Decimal(body["sand_pct"]) == Decimal("40")
    assert Decimal(body["silt_pct"]) == Decimal("40")
    assert Decimal(body["clay_pct"]) == Decimal("20")
    assert body["theta_fc"] is None
    assert body["theta_wp"] is None
    assert body["label"] == "not_enough_data"
    invalid = client.put(
        f"/v1/blocks/{block_id}/soil",
        headers={**headers, "If-Match": "1"},
        json={
            "texture_mode": "percent",
            "sand_pct": "40",
            "silt_pct": "40",
            "clay_pct": "30",
            "reason": "check the sum",
        },
    )
    assert invalid.status_code == 422
    assert invalid.json()["fields"]["sand_pct"] == "soil.percent_sum_invalid"


def test_root_depth_and_dry_down_ranges(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    _user, farm, headers = _owner(make_user, make_farm, auth_header, "range@agrect.app")
    block_id = _block_id(client, farm, headers)
    too_deep = client.put(
        f"/v1/blocks/{block_id}/soil",
        headers=headers,
        json={"texture_mode": "class", "root_depth_m": "5"},
    )
    assert too_deep.status_code == 422
    assert too_deep.json()["fields"]["root_depth_m"] == "soil.root_depth_out_of_range"
    shallow = client.put(
        f"/v1/blocks/{block_id}/soil",
        headers=headers,
        json={"texture_mode": "class", "root_depth_m": "0.09", "dry_down_pct": "9"},
    )
    assert shallow.status_code == 422
    assert shallow.json()["fields"]["root_depth_m"] == "soil.root_depth_out_of_range"
    assert shallow.json()["fields"]["dry_down_pct"] == "soil.dry_down_out_of_range"
    edges = client.put(
        f"/v1/blocks/{block_id}/soil",
        headers=headers,
        json={"texture_mode": "class", "root_depth_m": "0.1", "dry_down_pct": "90"},
    )
    assert edges.status_code == 200
    assert edges.json()["label"] == "not_enough_data"
    upper = client.put(
        f"/v1/blocks/{block_id}/soil",
        headers={**headers, "If-Match": "1"},
        json={
            "texture_mode": "class",
            "root_depth_m": "3.0",
            "dry_down_pct": "10",
            "reason": "upper bound",
        },
    )
    assert upper.status_code == 200


def test_irrigation_settings_and_version(
    client: TestClient,
    db: Session,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    user, farm, headers = _owner(make_user, make_farm, auth_header, "irrig@agrect.app")
    block_id = _block_id(client, farm, headers)
    rejected = client.put(
        f"/v1/blocks/{block_id}/irrigation-settings",
        headers=headers,
        json={"efficiency": "0", "kc": "0.70", "kc_source": "entered"},
    )
    assert rejected.status_code == 422
    assert rejected.json()["fields"]["efficiency"] == "irrigation.efficiency_out_of_range"
    high_kc = client.put(
        f"/v1/blocks/{block_id}/irrigation-settings",
        headers=headers,
        json={"efficiency": "0.9", "kc": "1.6", "kc_source": "entered"},
    )
    assert high_kc.status_code == 422
    assert high_kc.json()["fields"]["kc"] == "irrigation.kc_out_of_range"
    saved = client.put(
        f"/v1/blocks/{block_id}/irrigation-settings",
        headers=headers,
        json={"efficiency": "0.9", "kc": "0.70", "kc_source": "entered"},
    )
    assert saved.status_code == 200
    assert saved.headers["etag"] == "1"
    body = saved.json()
    assert Decimal(body["efficiency"]) == Decimal("0.9")
    assert Decimal(body["kc"]) == Decimal("0.70")
    assert body["kc_source"] == "entered"
    assert body["version"] == 1
    missing = client.put(
        f"/v1/blocks/{block_id}/irrigation-settings",
        headers=headers,
        json={"efficiency": "1", "kc": "0.70", "kc_source": "entered"},
    )
    assert missing.status_code == 428
    assert missing.json() == {"code": "conflict.version_required"}
    no_reason = client.put(
        f"/v1/blocks/{block_id}/irrigation-settings",
        headers={**headers, "If-Match": "1"},
        json={"efficiency": "1", "kc": "1.5", "kc_source": "entered"},
    )
    assert no_reason.status_code == 422
    assert no_reason.json()["fields"]["reason"] == "record.reason_required"
    updated = client.put(
        f"/v1/blocks/{block_id}/irrigation-settings",
        headers={**headers, "If-Match": "1"},
        json={"efficiency": "1", "kc": "1.5", "kc_source": "entered", "reason": "raise kc"},
    )
    assert updated.status_code == 200
    assert updated.json()["version"] == 2
    assert Decimal(updated.json()["efficiency"]) == Decimal("1")
    assert Decimal(updated.json()["kc"]) == Decimal("1.5")
    db.expire_all()
    history = db.scalars(
        select(RecordVersion).where(RecordVersion.entity_type == "irrigation_settings")
    ).one()
    assert history.version == 2
    assert history.user_id == user.id
    assert history.reason == "raise kc"
    assert "efficiency" in history.changed_fields
    assert "kc" in history.changed_fields


def test_other_user_cannot_read_soil(
    client: TestClient,
    make_user: Callable[[str, str], AppUser],
    make_farm: Callable[..., Farm],
    auth_header: Callable[[AppUser], dict[str, str]],
) -> None:
    _user_a, farm_a, headers_a = _owner(make_user, make_farm, auth_header, "owner@agrect.app")
    _user_b = make_user("other@agrect.app", "password-b")
    headers_b = auth_header(_user_b)
    block_id = _block_id(client, farm_a, headers_a)
    for path in ("soil", "irrigation-settings"):
        foreign_get = client.get(f"/v1/blocks/{block_id}/{path}", headers=headers_b)
        assert foreign_get.status_code == 404
        assert foreign_get.json() == {"code": "block.not_found"}
        foreign_put = client.put(
            f"/v1/blocks/{block_id}/{path}",
            headers={**headers_b, "If-Match": "1"},
            json={"texture_mode": "class"} if path == "soil" else {"efficiency": "0.9"},
        )
        assert foreign_put.status_code == 404
        assert foreign_put.json() == {"code": "block.not_found"}
    missing = client.get(f"/v1/blocks/{uuid.uuid4()}/soil", headers=headers_a)
    assert missing.status_code == 404
    assert missing.json() == {"code": "block.not_found"}
