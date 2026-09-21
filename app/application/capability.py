from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.application.capability_result import CapabilityResult
from app.application.execution_context import ExecutionContext


@runtime_checkable
class Capability(Protocol):
    """Executable application capability contract."""

    def execute(self, context: ExecutionContext) -> CapabilityResult:
        ...