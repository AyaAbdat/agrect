"""Load shared test vectors and compare Decimal results at the expected scale."""

import inspect
import json
from decimal import ROUND_HALF_UP, Decimal
from typing import TypedDict, cast

from app.core.config import REPO_ROOT


class VectorCase(TypedDict):
    id: str
    input: dict[str, str]
    expected: dict[str, str]


def load(group: str) -> list[VectorCase]:
    """Return the cases for one group in shared/test_vectors.json."""
    document = json.loads((REPO_ROOT / "shared" / "test_vectors.json").read_text(encoding="utf-8"))
    cases = document[group]
    if not isinstance(cases, list):
        raise TypeError(group)
    return cast(list[VectorCase], cases)


def D(x: str) -> Decimal:
    """Parse a test-vector number."""
    return Decimal(x)


def _decimal_places(expected: str) -> int:
    text = expected.strip()
    if text[:1] in "+-":
        text = text[1:]
    point = text.find(".")
    if point < 0:
        return 0
    return len(text[point + 1 :])


def _case_id_of(value: object) -> str | None:
    if isinstance(value, dict) and "id" in value and "expected" in value:
        return str(value["id"])
    return None


def _case_id() -> str:
    frame = inspect.currentframe()
    try:
        current = frame.f_back if frame is not None else None
        while current is not None:
            named = _case_id_of(current.f_locals.get("case"))
            if named is not None:
                return named
            for value in current.f_locals.values():
                found = _case_id_of(value)
                if found is not None:
                    return found
            current = current.f_back
    finally:
        del frame
    return "?"


def assert_matches(actual: Decimal | int, expected: str) -> None:
    """Round `actual` half-up to the scale of `expected` and require equality."""
    quantum = Decimal(1).scaleb(-_decimal_places(expected))
    rounded = Decimal(actual).quantize(quantum, rounding=ROUND_HALF_UP)
    assert rounded == Decimal(expected), (
        f"{_case_id()}: actual={actual} expected={expected} rounded={rounded}"
    )
