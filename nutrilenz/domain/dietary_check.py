from abc import ABC, abstractmethod


class DietaryCheck(ABC):
    """Polymorphic check definition; every check supplies groups to the same matcher."""

    group = "diet"

    @property
    @abstractmethod
    def key(self) -> str:
        """Stable key stored in a profile."""

    @property
    @abstractmethod
    def label(self) -> str:
        """Name shown in the form and result."""

    @property
    @abstractmethod
    def keyword_groups(self) -> tuple[str, ...]:
        """Names from the shared keyword catalogue."""
