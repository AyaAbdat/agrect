import json
from decimal import Decimal

from app.core.config import REPO_ROOT

EXPECTED_IDS = [
    "weather.vpd",
    "weather.gdd_average",
    "weather.gdd_average_upper",
    "soilwater.water_store",
    "soilwater.daily_balance",
    "soilwater.gross_irrigation",
    "soilwater.run_time_volume",
    "soilwater.runoff",
    "registry.density",
    "registry.round_down",
    "registry.drip_flow",
    "records.harvest_crates",
    "records.product_concentration",
]


def _assert_leaves(node: object, path: str) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            _assert_leaves(value, f"{path}.{key}")
        return
    if isinstance(node, list):
        for index, value in enumerate(node):
            _assert_leaves(value, f"{path}.{index}")
        return
    assert isinstance(node, str), path
    # records.harvest_crates input.unit is the category "crate", not a number.
    if path.endswith(".unit"):
        assert node == "crate"
        return
    Decimal(node)


def test_test_vectors() -> None:
    data = json.loads((REPO_ROOT / "shared" / "test_vectors.json").read_text(encoding="utf-8"))
    assert data["version"] == 1

    ids: list[str] = []
    for section in data.values():
        if not isinstance(section, list):
            continue
        for case in section:
            assert isinstance(case["id"], str)
            assert isinstance(case["input"], dict)
            assert isinstance(case["expected"], dict)
            ids.append(case["id"])
            _assert_leaves(case["input"], f"{case['id']}.input")
            _assert_leaves(case["expected"], f"{case['id']}.expected")

    assert len(ids) == len(set(ids)) == len(EXPECTED_IDS)
    assert set(ids) == set(EXPECTED_IDS)
