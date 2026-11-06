"""Exceptions shared by all managers. Each one carries a short error code."""


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


class AIError(NutriLenzError):
    """The AI step failed (no key, no connection, bad reply...)."""


class DataError(NutriLenzError):
    """Saving or loading failed (database down, duplicate name, missing record...)."""


class AuthError(NutriLenzError):
    """Login or sign-up failed."""


class ValidationError(NutriLenzError):
    """User input is invalid. Holds one message per form field."""

    def __init__(self, field_errors: dict[str, str]):
        super().__init__("INVALID_INPUT", "; ".join(field_errors.values()))
        self._field_errors = dict(field_errors)

    @property
    def field_errors(self) -> dict[str, str]:
        return dict(self._field_errors)


class ErrorMessages:
    """Turns error codes into text a user can understand."""

    _MESSAGES = {
        "CONFIGURATION_ERROR": "AI is not set up correctly (check the API keys and model names in .env).",
        "AUTHENTICATION_ERROR": "The AI service rejected the API key.",
        "API_CONNECTION_ERROR": "Could not reach the AI service. Check your internet connection.",
        "API_UNAVAILABLE": "The AI service is busy or unavailable. Please try again later.",
        "INVALID_RESPONSE": "The AI did not give a usable answer after the allowed attempts.",
        "NO_IMAGE_PROVIDER": "No AI service that can read images is set up.",
        "UNREADABLE_IMAGE": "The AI could not read a nutrition label in that photo. Try a clearer photo or type it in.",
        "DB_UNAVAILABLE": "The database cannot be reached right now. Please try again shortly.",
        "CORRUPT_DATA": "Some saved data is damaged and could not be loaded.",
        "DUPLICATE_USER": "That username is already taken.",
        "USER_NOT_FOUND": "That account no longer exists.",
        "RECORD_NOT_FOUND": "That record could not be found.",
        "BAD_LOGIN": "Wrong username or password.",
        "INVALID_INPUT": "Some details are not valid. Please check the form.",
        "JOB_NOT_FOUND": "That task could not be found. It may have expired.",
    }

    @classmethod
    def text(cls, code: str) -> str:
        return cls._MESSAGES.get(code, "Something went wrong (" + str(code) + ").")
