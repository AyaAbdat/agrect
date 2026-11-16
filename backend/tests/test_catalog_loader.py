import shutil
from collections.abc import Callable
from pathlib import Path

import pytest
import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.modules.catalog.loader import CATALOG_DIR, load_catalog
from app.modules.catalog.models import Crop, SoilTextureClass, TrainingSystem, Variety

# varieties.yaml lists 22 names (barley has two). The summary follows that list.
_OK = "catalog ok: 5 crops, 22 varieties, 10 training systems, 12 soil classes"


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
    return found


def test_load_twice(capsys: pytest.CaptureFixture[str]) -> None:
    load_catalog()
    with SessionLocal() as session:
        assert _counts(session) == (5, 22, 10, 12)
        first = _snapshot(session)
    load_catalog()
    with SessionLocal() as session:
        assert _counts(session) == (5, 22, 10, 12)
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
