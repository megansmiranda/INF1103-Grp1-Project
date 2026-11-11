import hmac
import secrets
from flask import session


class CsrfGuard:
    """Stops other websites from submitting forms as a logged-in user.
    Every form carries a token that must match the one in the session."""

    FIELD = "csrf_token"

    def token(self) -> str:
        if self.FIELD not in session:
            session[self.FIELD] = secrets.token_hex(16)
        return session[self.FIELD]

    def is_valid(self, submitted: str | None) -> bool:
        expected = session.get(self.FIELD)
        return bool(expected and submitted and hmac.compare_digest(expected, submitted))
