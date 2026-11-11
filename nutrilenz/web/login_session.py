from flask import session


class LoginSession:
    """Who is logged in, kept in the signed session cookie (only the user id)."""

    KEY = "user_id"

    def log_in(self, user_id: int) -> None:
        session.clear()
        session[self.KEY] = user_id

    def log_out(self) -> None:
        session.clear()

    @property
    def user_id(self) -> int | None:
        return session.get(self.KEY)
