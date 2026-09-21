from __future__ import annotations

from uuid import UUID

from app.domain.execution import Execution
from app.domain.repositories import ExecutionRepository, WorkflowRepository


class StartWorkflowExecution:
    """Starts a new workflow execution."""

    def __init__(
        self,
        workflow_repository: WorkflowRepository,
        execution_repository: ExecutionRepository,
    ) -> None:
        self._workflow_repository = workflow_repository
        self._execution_repository = execution_repository

    def execute(self, workflow_id: UUID) -> Execution:
        workflow = self._workflow_repository.get(workflow_id)
        if workflow is None:
            raise ValueError(f"Workflow not found: {workflow_id}")

        if workflow.state.name != "PUBLISHED":
            raise ValueError(f"Workflow must be published to execute: {workflow_id}")

        execution = Execution.create(workflow_id=workflow_id)
        self._execution_repository.save(execution)
        return execution
