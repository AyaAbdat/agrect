import shutil
from collections.abc import Callable
from pathlib import Path

import pytest
import yaml
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.modules.catalog.loader import CATALOG_DIR, load_catalog
from app.modules.catalog.models import (
    Crop,
    CropScale,
    CropScaleCode,
    SoilTextureClass,
    StageDd,
    StageDef,
    TrainingSystem,
    Variety,
    VarietyChill,
)

# varieties.yaml lists 22 names (barley has two). Stages are 9+9+9+11+11.
_OK = (
    "catalog ok: 5 crops, 22 varieties, 10 training systems, 12 soil classes, "
    "49 stages, 0 stage dd, 0 variety chill"
)


def _counts(session: Session) -> tuple[int, int, int, int]:
    return (
        len(session.scalars(select(Crop)).all()),
        len(session.scalars(select(Variety)).all()),
        len(session.scalars(select(TrainingSystem)).all()),
        len(session.scalars(select(SoilTextureClass)).all()),
    )


def _snapshot(session: Session) -> set[tuple[object, ...]]:
    found: set[tuple[object, ...]] = set()
    for row in session.execute(select(Crop.id, Crop.code, Crop.created_at, Crop.updated_at)):
        found.add(("crop", row.id, row.code, row.created_at, row.updated_at))
    for row in session.execute(
        select(Variety.id, Variety.code, Variety.created_at, Variety.updated_at)
    ):
        found.add(("variety", row.id, row.code, row.created_at, row.updated_at))
    for row in session.execute(
        select(
            TrainingSystem.id,
            TrainingSystem.code,
            TrainingSystem.created_at,
            TrainingSystem.updated_at,
        )
    ):
        found.add(("training", row.id, row.code, row.created_at, row.updated_at))
    for row in session.execute(
        select(
            SoilTextureClass.id,
            SoilTextureClass.code,
            SoilTextureClass.created_at,
            SoilTextureClass.updated_at,
        )
    ):
        found.add(("soil", row.id, row.code, row.created_at, row.updated_at))
    for row in session.execute(select(CropScale.crop_id, CropScale.scale, CropScale.citation)):
        found.add(("scale", row.crop_id, row.scale, row.citation))
    for row in session.execute(select(StageDef.id, StageDef.code, StageDef.name_en, StageDef.sort)):
        found.add(("stage", row.id, row.code, row.name_en, row.sort))
    for row in session.execute(select(StageDd.id)):
        found.add(("stage_dd", row.id))
    for row in session.execute(select(VarietyChill.variety_id, VarietyChill.citation)):
        found.add(("variety_chill", row.variety_id, row.citation))
    return found


def _stage_counts(session: Session) -> dict[str, int]:
    rows = session.execute(
        select(Crop.code, func.count(StageDef.id))
        .join(StageDef, StageDef.crop_id == Crop.id)
        .group_by(Crop.code)
    ).all()
    return {str(code): int(count) for code, count in rows}


def _scales(session: Session) -> dict[str, CropScaleCode]:
    rows = session.execute(
        select(Crop.code, CropScale.scale).join(CropScale, CropScale.crop_id == Crop.id)
    ).all()
    return {str(code): scale for code, scale in rows}


def test_load_twice(capsys: pytest.CaptureFixture[str]) -> None:
    load_catalog()
    with SessionLocal() as session:
        assert _counts(session) == (5, 22, 10, 12)
        assert _stage_counts(session) == {
            "table_grape": 9,
            "apple": 9,
            "olive": 9,
            "wheat": 11,
            "barley": 11,
        }
        assert sum(_stage_counts(session).values()) == 49
        assert _scales(session) == {
            "table_grape": CropScaleCode.el,
            "apple": CropScaleCode.bbch,
            "olive": CropScaleCode.bbch_olive,
            "wheat": CropScaleCode.zadoks,
            "barley": CropScaleCode.zadoks,
        }
        assert len(session.scalars(select(StageDd)).all()) == 0
        assert len(session.scalars(select(VarietyChill)).all()) == 0
        first = _snapshot(session)
    load_catalog()
    with SessionLocal() as session:
        assert _counts(session) == (5, 22, 10, 12)
        assert sum(_stage_counts(session).values()) == 49
        assert len(_scales(session)) == 5
        assert _snapshot(session) == first
    assert capsys.readouterr().out.count(_OK) == 2


class _QuotedDumper(yaml.SafeDumper):
    pass


def _repr_str(dumper: yaml.SafeDumper, data: str) -> yaml.nodes.ScalarNode:
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="'")


_QuotedDumper.add_representer(str, _repr_str)


def _copy_catalog(tmp_path: Path) -> Path:
    dest = tmp_path / "catalog"
    shutil.copytree(CATALOG_DIR, dest)
    return dest


def _rewrite(path: Path, mutate: Callable[[dict[str, object]], None]) -> None:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(raw, dict)
    mutate(raw)
    path.write_text(
        yaml.dump(raw, Dumper=_QuotedDumper, allow_unicode=True, sort_keys=False, width=4096),
        encoding="utf-8",
    )


def _soil(raw: dict[str, object], code: str) -> dict[str, object]:
    rows = raw["soil_textures"]
    assert isinstance(rows, list)
    for row in rows:
        assert isinstance(row, dict)
        if row.get("code") == code:
            return row
    raise AssertionError(code)


def test_soil_values_without_citation_writes_nothing(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    catalog = _copy_catalog(tmp_path)

    def strip_citation(raw: dict[str, object]) -> None:
        _soil(raw, "sand")["citation"] = None

    _rewrite(catalog / "soil_textures.yaml", strip_citation)
    with pytest.raises(SystemExit) as exc:
        load_catalog(catalog)
    assert exc.value.code == 1
    captured = capsys.readouterr().out
    assert "soil_textures.yaml: sand:" in captured
    assert "all be null" in captured
    with SessionLocal() as session:
        assert _counts(session) == (0, 0, 0, 0)


def test_soil_midpoint_mismatch_writes_nothing(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    catalog = _copy_catalog(tmp_path)

    def shift_midpoint(raw: dict[str, object]) -> None:
        _soil(raw, "loam")["theta_fc"] = "0.999"

    _rewrite(catalog / "soil_textures.yaml", shift_midpoint)
    with pytest.raises(SystemExit) as exc:
        load_catalog(catalog)
    assert exc.value.code == 1
    captured = capsys.readouterr().out
    assert "soil_textures.yaml: loam:" in captured
    assert "theta_fc is not the midpoint" in captured
    with SessionLocal() as session:
        assert _counts(session) == (0, 0, 0, 0)


def test_unknown_variety_crop_writes_nothing(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    catalog = _copy_catalog(tmp_path)

    def add_unknown(raw: dict[str, object]) -> None:
        rows = raw["varieties"]
        assert isinstance(rows, list)
        rows.append({"crop": "fig", "code": "bourjasotte", "name": "Bourjasotte", "sort": 1})

    _rewrite(catalog / "varieties.yaml", add_unknown)
    with pytest.raises(SystemExit) as exc:
        load_catalog(catalog)
    assert exc.value.code == 1
    captured = capsys.readouterr().out
    assert "varieties.yaml: fig/bourjasotte:" in captured
    assert "unknown crop 'fig'" in captured
    with SessionLocal() as session:
        assert _counts(session) == (0, 0, 0, 0)


def _cited_stage_dd(stage: str, citation: str | None) -> dict[str, object]:
    return {
        "crop": "olive",
        "stage": stage,
        "variety": None,
        "dd_value": "100",
        "base_c": "10",
        "upper_c": None,
        "method": "average",
        "source_kind": "literature",
        "citation": citation,
    }


def test_uncited_stage_dd_writes_nothing(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    catalog = _copy_catalog(tmp_path)

    def add_uncited(raw: dict[str, object]) -> None:
        rows = raw["stage_dd"]
        assert isinstance(rows, list)
        rows.append(_cited_stage_dd("65", None))

    _rewrite(catalog / "stage_dd.yaml", add_uncited)
    with pytest.raises(SystemExit) as exc:
        load_catalog(catalog)
    assert exc.value.code == 1
    captured = capsys.readouterr().out
    assert "stage_dd.yaml: olive/65:" in captured
    assert "citation is required" in captured
    with SessionLocal() as session:
        assert _counts(session) == (0, 0, 0, 0)
        assert len(session.scalars(select(StageDd)).all()) == 0


def test_unknown_stage_code_writes_nothing(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    catalog = _copy_catalog(tmp_path)

    def add_unknown(raw: dict[str, object]) -> None:
        rows = raw["stage_dd"]
        assert isinstance(rows, list)
        rows.append(
            _cited_stage_dd(
                "99",
                "Author A. (2000). Title. Journal 1:1–2, Table 1.",
            )
        )

    _rewrite(catalog / "stage_dd.yaml", add_unknown)
    with pytest.raises(SystemExit) as exc:
        load_catalog(catalog)
    assert exc.value.code == 1
    captured = capsys.readouterr().out
    assert "stage_dd.yaml: olive/99:" in captured
    assert "unknown stage '99'" in captured
    with SessionLocal() as session:
        assert _counts(session) == (0, 0, 0, 0)
        assert len(session.scalars(select(StageDef)).all()) == 0
