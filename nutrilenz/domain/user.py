from .profile import Profile


class User:
    """An account. Owns exactly one Profile. The password hash is private and is
    only checked through a PasswordHasher, never returned."""

    def __init__(self, username: str, password_hash: str, goal_specs: list[dict],
                 avoid_ingredients: list[str] | None = None, user_id: int | None = None):
        if not isinstance(username, str) or not username.strip():
            raise ValueError("Username is required")
        self._username = username.strip()
        self.__password_hash = password_hash
        self._profile = Profile(goal_specs, avoid_ingredients)
        self._user_id = user_id

    @property
    def user_id(self) -> int | None:
        return self._user_id

    def assign_id(self, user_id: int) -> None:
        if self._user_id is not None and self._user_id != user_id:
            raise ValueError("User already has an id")
        self._user_id = user_id

    @property
    def username(self) -> str:
        return self._username

    @property
    def profile(self) -> Profile:
        return self._profile

    def password_matches(self, password: str, hasher) -> bool:
        return hasher.verify(password, self.__password_hash)

    def password_hash_for_storage(self) -> str:
        """Only the Data Manager should call this, to save the account."""
        return self.__password_hash
