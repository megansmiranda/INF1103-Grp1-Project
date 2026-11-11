from .nutrilenz_error import NutriLenzError


class ValidationError(NutriLenzError):
    """User input is invalid. Holds one message per form field."""

    def __init__(self, field_errors: dict[str, str]):
        super().__init__("INVALID_INPUT", "; ".join(field_errors.values()))
        self._field_errors = dict(field_errors)

    @property
    def field_errors(self) -> dict[str, str]:
        return dict(self._field_errors)
