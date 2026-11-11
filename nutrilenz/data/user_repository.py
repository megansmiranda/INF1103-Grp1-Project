from abc import ABC, abstractmethod

from ..domain.user import User


class UserRepository(ABC):
    """Contract for storing accounts and their profiles."""

    @abstractmethod
    def add_user(self, user: User) -> User:
        """Save a new user and give it an id. DUPLICATE_USER if the name is taken."""

    @abstractmethod
    def find_user(self, username: str) -> User | None:
        """Look up by username, ignoring capital letters."""

    @abstractmethod
    def get_user(self, user_id: int) -> User | None:
        """Look up by id."""

    @abstractmethod
    def update_profile(self, user: User) -> None:
        """Save the user's current goals and avoid list."""

    @abstractmethod
    def delete_user(self, user_id: int) -> bool:
        """Remove the account, its goals and its analyses. Products stay."""

    @abstractmethod
    def count_users(self) -> int:
        """How many accounts exist."""
