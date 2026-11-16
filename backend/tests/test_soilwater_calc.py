from decimal import Decimal

import pytest

from app.modules.soilwater.calc import (
    CalcInputError,
    daily_balance,
    depth_mm,
    etc_mm,
    gross_mm,
    irrigate_below_mm,
    raw_mm,
    run_time_min,
    soil_check_reset_mm,
    soil_entering,
    status,
    taw_mm,
    volume_m3,
    water_left_mm,
)
from tests.vectors import D, VectorCase, assert_matches, load


@pytest.mark.parametrize("case", load("soilwater"), ids=lambda case: case["id"])
def test_soilwater_vector(case: VectorCase) -> None:
    raw = case["input"]
    expected = case["expected"]
    if case["id"] == "soilwater.water_store":
        taw = taw_mm(D(raw["theta_fc"]), D(raw["theta_wp"]), D(raw["root_depth_m"]))
        assert isinstance(taw, Decimal)
        assert_matches(taw, expected["taw_mm"])
        assert_matches(raw_mm(D(raw["p"]), taw), expected["raw_mm"])
    elif case["id"] == "soilwater.daily_balance":
        # 150 mm is the water-store capacity and sits above the unclamped 31 mm.
        taw = D(raw["taw_mm"]) if "taw_mm" in raw else D("150")
        dr_mm, drainage_mm = daily_balance(
            D(raw["dr_prev_mm"]),
            D(raw["rain_mm"]),
            D(raw["irrigation_soil_mm"]),
            D(raw["etc_mm"]),
            taw,
        )
        assert_matches(dr_mm, expected["dr_mm"])
        assert drainage_mm == D("0")
    elif case["id"] == "soilwater.gross_irrigation":
        assert_matches(gross_mm(D(raw["etc_mm"]), D(raw["efficiency"])), expected["gross_mm"])
    elif case["id"] == "soilwater.run_time_volume":
        assert_matches(
            volume_m3(D(raw["q_m3h"]), D(raw["duration_min"])),
            expected["volume_m3"],
        )
    elif case["id"] == "soilwater.runoff":
        soil_mm, runoff_mm = soil_entering(
            D(raw["rate_mm_h"]),
            D(raw["duration_min"]),
            D(raw["efficiency"]),
            D(raw["infiltration_mm_h"]),
        )
        assert_matches(soil_mm, expected["soil_mm"])
        assert_matches(runoff_mm, expected["runoff_mm"])
    else:
        raise AssertionError(case["id"])


def test_rain_above_depletion_drains() -> None:
    dr_mm, drainage_mm = daily_balance(D("10"), D("25"), D("0"), D("0"), D("150"))
    assert dr_mm == D("0")
    assert drainage_mm > 0
    assert drainage_mm == D("15")


def test_depletion_beyond_taw_clamps() -> None:
    dr_mm, drainage_mm = daily_balance(D("140"), D("0"), D("0"), D("20"), D("150"))
    assert dr_mm == D("150")
    assert drainage_mm == D("0")


def test_status_boundary_is_irrigate_soon() -> None:
    assert status(D("75"), D("75")) == "irrigate_soon"
    assert status(D("74"), D("75")) == "ok"


def test_soil_check_bands() -> None:
    taw = D("150")
    assert soil_check_reset_mm(taw, "dry") == D("131.25")
    assert soil_check_reset_mm(taw, "slightly_moist") == D("93.75")
    assert soil_check_reset_mm(taw, "moist") == D("56.25")
    assert soil_check_reset_mm(taw, "wet") == D("18.75")


def test_efficiency_out_of_range() -> None:
    for efficiency in (D("0"), D("1.2"), D("-0.1")):
        with pytest.raises(CalcInputError) as raised:
            gross_mm(D("7"), efficiency)
        assert raised.value.field == "efficiency"
        assert raised.value.code == "soilwater.efficiency_out_of_range"
    with pytest.raises(CalcInputError) as raised:
        soil_entering(D("12"), D("60"), D("1.2"), D("8"))
    assert raised.value.code == "soilwater.efficiency_out_of_range"


def test_non_positive_inputs() -> None:
    with pytest.raises(CalcInputError) as raised:
        taw_mm(D("0.30"), D("0.15"), D("0"))
    assert raised.value.code == "soilwater.root_depth_m_must_be_positive"
    with pytest.raises(CalcInputError) as raised:
        raw_mm(D("0"), D("150"))
    assert raised.value.code == "soilwater.p_must_be_positive"
    dr_mm, drainage_mm = daily_balance(D("10"), D("0"), D("0"), D("0"), D("150"))
    assert dr_mm == D("10")
    assert drainage_mm == D("0")


def test_water_left_and_irrigate_below() -> None:
    assert water_left_mm(D("130"), D("20")) == D("110")
    assert water_left_mm(D("130"), D("0")) == D("130")
    assert irrigate_below_mm(D("130"), D("65")) == D("65")
    with pytest.raises(CalcInputError) as raised:
        water_left_mm(D("0"), D("1"))
    assert raised.value.code == "soilwater.taw_mm_must_be_positive"
    with pytest.raises(CalcInputError) as raised:
        water_left_mm(D("130"), D("-1"))
    assert raised.value.field == "dr_mm"
    assert raised.value.code == "soilwater.dr_mm_must_be_positive"
    with pytest.raises(CalcInputError) as raised:
        irrigate_below_mm(D("-1"), D("10"))
    assert raised.value.code == "soilwater.taw_mm_must_be_positive"
    with pytest.raises(CalcInputError) as raised:
        irrigate_below_mm(D("130"), D("-1"))
    assert raised.value.field == "raw_mm"
    assert raised.value.code == "soilwater.raw_mm_must_be_positive"


def test_depth_runtime_and_etc() -> None:
    assert etc_mm(D("5"), D("0.8")) == D("4.0")
    assert depth_mm(D("12"), D("60")) == D("12")
    assert run_time_min(D("10"), D("5")) == D("120")
    soil_mm, runoff_mm = soil_entering(D("10"), D("60"), D("0.5"))
    assert soil_mm == D("5")
    assert runoff_mm == D("0")
