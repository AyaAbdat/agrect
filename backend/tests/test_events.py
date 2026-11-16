import pytest

from app.core.events import publish, subscribe, unsubscribe


def test_publish_runs_handlers_in_order_before_returning() -> None:
    seen: list[str] = []

    def first(payload: dict[str, object]) -> None:
        seen.append(f"first:{payload['n']}")

    def second(payload: dict[str, object]) -> None:
        seen.append(f"second:{payload['n']}")

    subscribe("waterbalance.updated", first)
    subscribe("waterbalance.updated", second)
    try:
        publish("waterbalance.updated", {"n": 1})
        assert seen == ["first:1", "second:1"]
    finally:
        unsubscribe("waterbalance.updated", first)
        unsubscribe("waterbalance.updated", second)


def test_handler_exception_reaches_the_caller() -> None:
    def boom(_payload: dict[str, object]) -> None:
        raise RuntimeError("balance failed")

    subscribe("waterbalance.updated", boom)
    try:
        with pytest.raises(RuntimeError, match="balance failed"):
            publish("waterbalance.updated", {})
    finally:
        unsubscribe("waterbalance.updated", boom)


def test_unknown_event_name_is_rejected() -> None:
    with pytest.raises(ValueError):
        subscribe("not.an.event", lambda _payload: None)
    with pytest.raises(ValueError):
        publish("not.an.event", {})
