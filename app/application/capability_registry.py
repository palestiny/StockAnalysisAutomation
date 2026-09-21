from __future__ import annotations

from typing import Protocol

from app.application.capability import Capability


class CapabilityRegistry:
    """Registry for capability implementations."""

    def __init__(self) -> None:
        self._capabilities: dict[str, Capability] = {}

    def register(self, capability_id: str, capability: Capability) -> None:
        if not capability_id:
            raise ValueError("capability_id cannot be empty")
        if not isinstance(capability, Capability):
            raise TypeError("capability must implement Capability protocol")
        self._capabilities[capability_id] = capability

    def get(self, capability_id: str) -> Capability:
        if capability_id not in self._capabilities:
            raise KeyError(f"Capability not found: {capability_id}")
        return self._capabilities[capability_id]

    def has(self, capability_id: str) -> bool:
        return capability_id in self._capabilities