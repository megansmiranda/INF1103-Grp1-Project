from abc import ABC, abstractmethod

from ..domain.analysis import Analysis
from ..domain.flag import Flag


class AnalysisRepository(ABC):
    """Contract for saved analysis records."""

    @abstractmethod
    def add_analysis(self, analysis: Analysis) -> Analysis:
        """Save a record (its product must already have an id) and give it an id."""

    @abstractmethod
    def list_analyses(self, user_id: int, flag: Flag | None = None,
                      search: str | None = None) -> list[Analysis]:
        """A user's records, newest first, optionally filtered by flag and product name."""

    @abstractmethod
    def get_analysis(self, user_id: int, analysis_id: int) -> Analysis | None:
        """One record, only if it belongs to the user."""

    @abstractmethod
    def delete_analysis(self, user_id: int, analysis_id: int) -> bool:
        """Remove one record. False if it was not found."""
