from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class ScheduledExecutionRequest:
    workflow_id: UUID
    scheduled_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.workflow_id, UUID):
            raise ValueError("ScheduledExecutionRequest workflow_id must be a UUID")
        if not isinstance(self.scheduled_at, datetime):
            raise ValueError(
                "ScheduledExecutionRequest scheduled_at must be a datetime"
            )

    @classmethod
    def create(
        cls,
        workflow_id: UUID,
        scheduled_at: datetime,
    ) -> "ScheduledExecutionRequest":
        return cls(workflow_id=workflow_id, scheduled_at=scheduled_at)


class Clock(Protocol):
    def now(self) -> datetime:
        ...


class FixedClock:
    def __init__(self, current_time: datetime) -> None:
        self._current_time = current_time

    def now(self) -> datetime:
        return self._current_time


class Schedule:
    def __init__(self, request: ScheduledExecutionRequest) -> None:
        self.request = request

    def is_due(self, clock: Clock) -> bool:
        return clock.now() >= self.request.scheduled_at