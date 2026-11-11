from abc import ABC, abstractmethod

from .user_repository import UserRepository
from .product_repository import ProductRepository
from .analysis_repository import AnalysisRepository


class DataStore(UserRepository, ProductRepository, AnalysisRepository, ABC):
    """A complete storage back end. Any DataStore can replace another."""

    @abstractmethod
    def initialise(self) -> None:
        """Connect and create tables if needed. DB_UNAVAILABLE if it cannot."""
