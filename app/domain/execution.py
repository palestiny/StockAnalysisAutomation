from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4


class ExecutionState(Enum):
    CREATED = "created"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


@dataclass
class Execution:
    id: UUID
    workflow_id: UUID
    state: ExecutionState
    current_step: int
    attempt: int
    created_at: datetime
    updated_at: datetime
    error: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.id, UUID):
            raise TypeError("id must be a UUID")
        if not isinstance(self.workflow_id, UUID):
            raise TypeError("workflow_id must be a UUID")
        if not isinstance(self.state, ExecutionState):
            raise TypeError("state must be an ExecutionState")
        if not isinstance(self.current_step, int) or self.current_step < 0:
            raise ValueError("current_step must be a non-negative integer")
        if not isinstance(self.attempt, int) or self.attempt < 1:
            raise ValueError("attempt must be a positive integer")
        if not isinstance(self.created_at, datetime):
            raise TypeError("created_at must be a datetime")
        if not isinstance(self.updated_at, datetime):
            raise TypeError("updated_at must be a datetime")

    @classmethod
    def create(cls, workflow_id: UUID, attempt: int = 1) -> Execution:
        now = datetime.utcnow()
        return cls(
            id=uuid4(),
            workflow_id=workflow_id,
            state=ExecutionState.CREATED,
            current_step=0,
            attempt=attempt,
            created_at=now,
            updated_at=now,
        )

    def start(self) -> None:
        if self.state != ExecutionState.CREATED:
            raise ValueError(f"Cannot start execution in state: {self.state}")
        self.state = ExecutionState.RUNNING
        self.updated_at = datetime.utcnow()

    def complete_step(self) -> None:
        if self.state != ExecutionState.RUNNING:
            raise ValueError(f"Cannot complete step in state: {self.state}")
        self.current_step += 1
        self.updated_at = datetime.utcnow()

    def fail(self, error: str) -> None:
        if self.state not in (ExecutionState.RUNNING, ExecutionState.WAITING, ExecutionState.RETRYING):
            raise ValueError(f"Cannot fail execution in state: {self.state}")
        self.state = ExecutionState.FAILED
        self.error = error
        self.updated_at = datetime.utcnow()

    def complete(self) -> None:
        if self.state != ExecutionState.RUNNING:
            raise ValueError(f"Cannot complete execution in state: {self.state}")
        self.state = ExecutionState.COMPLETED
        self.updated_at = datetime.utcnow()

    def cancel(self) -> None:
        if self.state in (ExecutionState.COMPLETED, ExecutionState.FAILED, ExecutionState.CANCELLED):
            raise ValueError(f"Cannot cancel execution in state: {self.state}")
        self.state = ExecutionState.CANCELLED
        self.updated_at = datetime.utcnow()

    def wait(self) -> None:
        if self.state != ExecutionState.RUNNING:
            raise ValueError(f"Cannot wait execution in state: {self.state}")
        self.state = ExecutionState.WAITING
        self.updated_at = datetime.utcnow()

    def resume(self) -> None:
        if self.state != ExecutionState.WAITING:
            raise ValueError(f"Cannot resume execution in state: {self.state}")
        self.state = ExecutionState.RUNNING
        self.updated_at = datetime.utcnow()

    def retry(self) -> None:
        if self.state != ExecutionState.FAILED:
            raise ValueError(f"Cannot retry execution in state: {self.state}")
        self.state = ExecutionState.RETRYING
        self.attempt += 1
        self.current_step = 0
        self.error = None
        self.updated_at = datetime.utcnow()
