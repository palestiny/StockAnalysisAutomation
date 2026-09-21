from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.domain.execution import Execution
from app.domain.execution_event import ExecutionEvent
from app.domain.repositories import (
    ExecutionHistoryRepository,
    ExecutionIdempotencyRecord,
    ExecutionIdempotencyRepository,
    ExecutionRepository,
    WorkflowRepository,
)
from app.domain.workflow import Workflow


class InMemoryWorkflowRepository(WorkflowRepository):
    def __init__(self) -> None:
        self._workflows: dict[UUID, Workflow] = {}

    def save(self, workflow: Workflow) -> None:
        self._workflows[workflow.id] = workflow

    def get(self, workflow_id: UUID) -> Workflow | None:
        return self._workflows.get(workflow_id)

    def all(self) -> tuple[Workflow, ...]:
        return tuple(self._workflows.values())


class InMemoryExecutionRepository(ExecutionRepository):
    def __init__(self) -> None:
        self._executions: dict[UUID, Execution] = {}

    def save(self, execution: Execution) -> None:
        self._executions[execution.id] = execution

    def get(self, execution_id: UUID) -> Execution | None:
        return self._executions.get(execution_id)

    def all(self) -> tuple[Execution, ...]:
        return tuple(self._executions.values())


class InMemoryExecutionIdempotencyRepository(ExecutionIdempotencyRepository):
    def __init__(self) -> None:
        self._records: dict[str, ExecutionIdempotencyRecord] = {}

    def get(self, key: str) -> ExecutionIdempotencyRecord | None:
        return self._records.get(key)

    def reserve(
        self,
        key: str,
        workflow_id: UUID,
        execution_id: UUID,
    ) -> tuple[ExecutionIdempotencyRecord, bool]:
        existing = self._records.get(key)
        if existing is not None:
            if existing.workflow_id == workflow_id:
                return existing, False
            raise ValueError(f"Idempotency key {key} already used for different workflow")
        record = ExecutionIdempotencyRecord(
            key=key,
            workflow_id=workflow_id,
            execution_id=execution_id,
            created_at=datetime.utcnow(),
        )
        self._records[key] = record
        return record, True

    def release(self, key: str, execution_id: UUID) -> None:
        record = self._records.get(key)
        if record is not None and record.execution_id == execution_id:
            del self._records[key]


class InMemoryExecutionHistoryRepository(ExecutionHistoryRepository):
    def __init__(self) -> None:
        self._events: dict[UUID, list[ExecutionEvent]] = {}

    def append(self, event: ExecutionEvent) -> None:
        if event.execution_id not in self._events:
            self._events[event.execution_id] = []
        self._events[event.execution_id].append(event)

    def list(self, execution_id: UUID) -> tuple[ExecutionEvent, ...]:
        return tuple(self._events.get(execution_id, []))
