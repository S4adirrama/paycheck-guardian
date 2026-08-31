"""Deterministic, redacted event recording for offline agent runs."""

from collections.abc import Mapping
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from .models import TrajectoryEvent


_SENSITIVE_KEY_PARTS = ("api_key", "token", "secret", "authorization")
_REDACTED = "***REDACTED***"
_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def _is_sensitive_key(key: object) -> bool:
    return isinstance(key, str) and any(part in key.lower() for part in _SENSITIVE_KEY_PARTS)


def redact(value: Any) -> Any:
    """Return a JSON-safe value with credential-shaped dictionary fields hidden."""
    if isinstance(value, Mapping):
        return {
            str(key): _REDACTED if _is_sensitive_key(key) else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if hasattr(value, "model_dump"):
        return redact(value.model_dump(mode="json"))
    return value


class TrajectoryRecorder:
    """Append structured events using deterministic timestamps for reproducible evaluation."""

    def __init__(self, run_id: str, events: list[TrajectoryEvent] | None = None) -> None:
        self.run_id = run_id
        self.events = list(events or [])

    def record(
        self,
        *,
        component: str,
        event_type: str,
        instruction: str | None = None,
        tool_name: str | None = None,
        tool_input: dict[str, Any] | None = None,
        tool_result: dict[str, Any] | None = None,
        verification_feedback: list[str] | None = None,
        attempt: int = 1,
        human_checkpoint: str | None = None,
    ) -> TrajectoryEvent:
        """Record an event and recursively redact any sensitive values before storage."""
        event = TrajectoryEvent(
            timestamp=_EPOCH + timedelta(microseconds=len(self.events)),
            run_id=self.run_id,
            component=component,
            event_type=event_type,
            instruction=instruction,
            tool_name=tool_name,
            tool_input=redact(tool_input or {}),
            tool_result=redact(tool_result or {}),
            verification_feedback=list(verification_feedback or []),
            attempt=attempt,
            human_checkpoint=human_checkpoint,
        )
        self.events.append(event)
        return event
