from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable
from uuid import UUID

from app.domain.execution import Execution
from app.domain.workflow import Workflow


@runtime_checkable
class WorkflowRepository(Protocol):
    """Persistence boundary for Workflow aggregates."""

    def save(self, workflow: Workflow) -> None:
        ...

    def get(self, workflow_id: UUID) -> Workflow | None:
        ...

    def all(self) -> tuple[Workflow, ...]:
        ...


@runtime_checkable
class ExecutionRepository(Protocol):
    """Persistence boundary for Execution aggregates."""

    def save(self, execution: Execution) -> None:
        ...

    def get(self, execution_id: UUID) -> Execution | None:
        ...

    def all(self) -> tuple[Execution, ...]:
        ...


@dataclass(frozen=True)
class ExecutionIdempotencyRecord:
    """Binding between an idempotency key and its created execution."""

    key: str
    workflow_id: UUID
    execution_id: UUID
    created_at: datetime


@runtime_checkable
class ExecutionIdempotencyRepository(Protocol):
    """Persistence boundary for workflow-start idempotency keys."""

    def get(self, key: str) -> ExecutionIdempotencyRecord | None:
        ...

    def reserve(
        self,
        key: str,
        workflow_id: UUID,
        execution_id: UUID,
    ) -> tuple[ExecutionIdempotencyRecord, bool]:
        ...

    def release(self, key: str, execution_id: UUID) -> None:
        ...


@runtime_checkable
class ExecutionHistoryRepository(Protocol):
    """Append-only persistence boundary for execution lifecycle evidence."""

    def append(self, event) -> None:
        ...

    def list(self, execution_id: UUID) -> tuple:
        ...