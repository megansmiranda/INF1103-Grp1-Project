class AIResult:
    """A validated task result plus which provider produced it."""

    def __init__(self, value, provider: str):
        self._value = value
        self._provider = provider

    @property
    def value(self):
        return self._value

    @property
    def provider(self) -> str:
        return self._provider
