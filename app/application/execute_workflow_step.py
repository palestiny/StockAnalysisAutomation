from __future__ import annotations

from uuid import UUID

from app.application.capability_dispatcher import CapabilityDispatcher
from app.application.condition_evaluator import ConditionEvaluator
from app.application.execution_context import ExecutionContext
from app.domain.execution import Execution
from app.domain.repositories import ExecutionRepository, WorkflowRepository
from app.domain.workflow import Workflow, WorkflowStep


class ExecuteWorkflowStep:
    """Executes a single workflow step."""

    def __init__(
        self,
        workflow_repository: WorkflowRepository,
        execution_repository: ExecutionRepository,
        dispatcher: CapabilityDispatcher,
        condition_evaluator: ConditionEvaluator,
    ) -> None:
        self._workflow_repository = workflow_repository
        self._execution_repository = execution_repository
        self._dispatcher = dispatcher
        self._condition_evaluator = condition_evaluator

    def execute(
        self,
        execution_id: UUID,
        context: ExecutionContext,
    ) -> Execution:
        execution = self._execution_repository.get(execution_id)
        if execution is None:
            raise ValueError(f"Execution not found: {execution_id}")

        if execution.state.name != "RUNNING":
            raise ValueError(f"Execution must be running: {execution_id}")

        workflow = self._workflow_repository.get(execution.workflow_id)
        if workflow is None:
            raise ValueError(f"Workflow not found: {execution.workflow_id}")

        current_step_index = execution.current_step
        if current_step_index >= len(workflow.steps):
            raise ValueError("No more steps to execute")

        step = workflow.steps[current_step_index]

        if step.condition is not None:
            try:
                if not self._condition_evaluator.evaluate(step.condition, context):
                    execution.complete_step()
                    self._execution_repository.save(execution)
                    return execution
            except KeyError:
                execution.fail("Missing context value for condition")
                self._execution_repository.save(execution)
                return execution

        result = self._dispatcher.dispatch(step.capability, context)

        if result.succeeded:
            execution.complete_step()
        else:
            execution.fail(str(result.error))

        self._execution_repository.save(execution)
        return execution