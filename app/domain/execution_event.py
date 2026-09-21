from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID


class ExecutionEventType(Enum):
    STARTED = "started"
    STEP_COMPLETED = "step_completed"
    WAITING = "waiting"
    RESUMED = "resumed"
    RETRYING = "retrying"
    FAILED = "failed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class ExecutionEvent:
    execution_id: UUID
    workflow_id: UUID
    event_type: ExecutionEventType
    sequence: int
    state: str
    attempt: int
    timestamp: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.execution_id, UUID):
            raise TypeError("execution_id must be a UUID")
        if not isinstance(self.workflow_id, UUID):
            raise TypeError("workflow_id must be a UUID")
        if not isinstance(self.event_type, ExecutionEventType):
            raise TypeError("event_type must be an ExecutionEventType")
        if not isinstance(self.sequence, int) or self.sequence < 0:
            raise ValueError("sequence must be a non-negative integer")
        if not isinstance(self.state, str):
            raise TypeError("state must be a string")
        if not isinstance(self.attempt, int) or self.attempt < 1:
            raise ValueError("attempt must be a positive integer")
        if not isinstance(self.timestamp, datetime):
            raise TypeError("timestamp must be a datetime")