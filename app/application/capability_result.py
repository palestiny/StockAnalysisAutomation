from __future__ import annotations


class CapabilityResult:
    def __init__(
        self,
        succeeded: bool,
        error: str | Exception | None = None,
    ) -> None:
        self.succeeded = succeeded
        self.error = error

    @classmethod
    def success(cls) -> "CapabilityResult":
        return cls(succeeded=True)

    @classmethod
    def failure(cls, error: str | Exception) -> "CapabilityResult":
        return cls(
            succeeded=False,
            error=error,
        )