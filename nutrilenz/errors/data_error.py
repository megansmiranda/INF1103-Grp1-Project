from .nutrilenz_error import NutriLenzError


class DataError(NutriLenzError):
    """Saving or loading failed (database down, duplicate name, missing record...)."""
