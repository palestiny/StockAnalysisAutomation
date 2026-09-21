class ExecutionContext:
    """Execution-scoped application state shared across workflow steps."""

    def __init__(self) -> None:
        self._data: dict[str, object] = {}

    def set(self, key: str, value: object) -> None:
        """Store a value under an execution context key."""
        self._data[key] = value

    def get(self, key: str) -> object:
        """Return a stored value or raise KeyError when the key is absent."""
        return self._data[key]

    def get_or_none(self, key: str) -> object | None:
        """Return a stored value or None when the key is absent."""
        return self._data.get(key)