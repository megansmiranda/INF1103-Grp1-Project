from .nutrilenz_error import NutriLenzError


class AIError(NutriLenzError):
    """The AI step failed (no key, no connection, bad reply...)."""
