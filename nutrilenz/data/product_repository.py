from abc import ABC, abstractmethod

from ..domain.product import Product


class ProductRepository(ABC):
    """Contract for the shared product catalogue."""

    @abstractmethod
    def add_product(self, product: Product) -> Product:
        """Save a product and give it an id."""

    @abstractmethod
    def get_product(self, product_id: int) -> Product | None:
        """Look up by id."""

    @abstractmethod
    def list_products(self) -> list[Product]:
        """Every saved product."""
