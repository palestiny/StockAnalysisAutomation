from __future__ import annotations

from app.application.capability import Capability
from app.application.capability_registry import CapabilityRegistry
from app.application.capability_result import CapabilityResult
from app.application.execution_context import ExecutionContext


class CapabilityDispatcher:
    """Dispatches capability execution requests to registered implementations."""

    def __init__(self, registry: CapabilityRegistry) -> None:
        self._registry = registry

    def dispatch(
        self,
        capability_id: str,
        context: ExecutionContext,
    ) -> CapabilityResult:
        capability = self._registry.get(capability_id)
        return capability.execute(context)