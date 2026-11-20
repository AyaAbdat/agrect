"""In-process event dispatcher.

Handlers run synchronously on the caller's stack. Pass the open SQLAlchemy
session in the payload so a handler reads and writes inside the caller's
transaction; handlers must not commit.

Event names match the system design: ``weather.daily_ready``,
``irrigation.logged``, ``waterbalance.updated``, ``block.updated``,
``stage.observed``, ``stage.predicted``.
"""

from collections import defaultdict
from collections.abc import Callable
from typing import Any

Handler = Callable[[dict[str, Any]], None]

EVENT_NAMES = frozenset(
    {
        "weather.daily_ready",
        "irrigation.logged",
        "waterbalance.updated",
        "block.updated",
        "stage.observed",
        "stage.predicted",
    }
)

_handlers: dict[str, list[Handler]] = defaultdict(list)


def subscribe(name: str, handler: Handler) -> None:
    """Register ``handler`` for ``name``. The same handler is not added twice."""
    if name not in EVENT_NAMES:
        raise ValueError(name)
    bucket = _handlers[name]
    if handler not in bucket:
        bucket.append(handler)


def unsubscribe(name: str, handler: Handler) -> None:
    """Remove one handler. Used by tests so they do not leak subscriptions."""
    if name not in EVENT_NAMES:
        raise ValueError(name)
    _handlers[name] = [item for item in _handlers[name] if item is not handler]


def publish(name: str, payload: dict[str, Any]) -> None:
    """Call every handler for ``name`` before returning.

    A handler exception propagates to the caller, which can roll back.
    """
    if name not in EVENT_NAMES:
        raise ValueError(name)
    for handler in tuple(_handlers[name]):
        handler(payload)
