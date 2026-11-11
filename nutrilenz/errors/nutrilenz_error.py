class NutriLenzError(Exception):
    """Base error. The code is what the IO Manager turns into a friendly message."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(detail or code)
        self._code = code
        self._detail = detail

    @property
    def code(self) -> str:
        return self._code

    @property
    def detail(self) -> str:
        return self._detail
