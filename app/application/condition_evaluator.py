from __future__ import annotations

from typing import Any

from app.application.execution_context import ExecutionContext
from app.domain.workflow import Condition


class ConditionEvaluator:
    """Evaluates workflow step conditions against execution context."""

    def evaluate(self, condition: Condition | None, context: ExecutionContext) -> bool:
        if condition is None:
            return True

        left_value: Any = self._get_value(condition.left_operand, context)
        right_value: Any = condition.right_operand

        if condition.operator == "equals":
            return bool(left_value == right_value)
        elif condition.operator == "not_equals":
            return bool(left_value != right_value)
        elif condition.operator == "greater_than":
            return bool(left_value > right_value)
        elif condition.operator == "greater_than_or_equal":
            return bool(left_value >= right_value)
        elif condition.operator == "less_than":
            return bool(left_value < right_value)
        elif condition.operator == "less_than_or_equal":
            return bool(left_value <= right_value)
        else:
            raise ValueError(f"Unsupported operator: {condition.operator}")

    def _get_value(self, key: str, context: ExecutionContext) -> Any:
        return context.get(key)
