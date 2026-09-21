from __future__ import annotations

from app.application.execution_context import ExecutionContext


class ConditionEvaluator:
    """Evaluates workflow step conditions against execution context."""

    def evaluate(self, condition, context: ExecutionContext) -> bool:
        if condition is None:
            return True

        left_value = self._get_value(condition.left_operand, context)
        right_value = condition.right_operand

        if condition.operator == "equals":
            return left_value == right_value
        elif condition.operator == "not_equals":
            return left_value != right_value
        elif condition.operator == "greater_than":
            return left_value > right_value
        elif condition.operator == "greater_than_or_equal":
            return left_value >= right_value
        elif condition.operator == "less_than":
            return left_value < right_value
        elif condition.operator == "less_than_or_equal":
            return left_value <= right_value
        else:
            raise ValueError(f"Unsupported operator: {condition.operator}")

    def _get_value(self, key: str, context: ExecutionContext):
        return context.get(key)