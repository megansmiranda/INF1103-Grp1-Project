from .product_suggestion import ProductSuggestion
from .recommendation_options import RecommendationOptions
from .scored_product import ScoredProduct


class Recommendation:
    """A shortlist of saved products for one user plus AI tips.
    It only holds references to products that already exist in the catalogue,
    so removing the shortlist never removes a product (aggregation)."""

    def __init__(self, user_id: int, options: RecommendationOptions | None = None):
        self._user_id = user_id
        self._options = options or RecommendationOptions()
        self._items: list[ScoredProduct] = []
        self._reasons: dict[int, str] = {}
        self._tips: list[str] = []
        self._suggested_products: list[ProductSuggestion] = []

    @property
    def user_id(self) -> int:
        return self._user_id

    @property
    def options(self) -> RecommendationOptions:
        return self._options

    @property
    def options_text(self) -> str:
        return self._options.describe_focus() + " · " + self._options.describe_categories()

    def add(self, item: ScoredProduct) -> None:
        """Items keep the order they are added in (the Logic Manager's ranking)."""
        self._items.append(item)

    def items(self) -> tuple[ScoredProduct, ...]:
        return tuple(self._items)

    def product_ids(self) -> list[int]:
        return [item.product.product_id for item in self._items]

    def set_reason(self, product_id: int, reason: str) -> None:
        if product_id not in self.product_ids():
            raise ValueError("Product is not in this recommendation")
        self._reasons[product_id] = reason

    def reason_for(self, product_id: int) -> str | None:
        return self._reasons.get(product_id)

    def set_tips(self, tips: list[str]) -> None:
        self._tips = list(tips)

    @property
    def tips(self) -> tuple[str, ...]:
        return tuple(self._tips)

    def set_suggested_products(self, products: list[ProductSuggestion]) -> None:
        """Products from outside the catalogue that the AI suggests (not checked)."""
        self._suggested_products = list(products)

    @property
    def suggested_products(self) -> tuple[ProductSuggestion, ...]:
        return tuple(self._suggested_products)

    def is_empty(self) -> bool:
        return not self._items
