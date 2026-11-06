from enum import Enum

from .analysis import GoalResult, ProductSuggestion
from .nutrients import Nutrient
from .product import Product


class RecommendationFocus(Enum):
    """Fixed choices the user picks from instead of typing a free-text question."""

    BEST_MATCH = ("Best match for my goals", None, None)
    LOWEST_SUGAR = ("Lowest sugar", Nutrient.SUGAR, "LOW")
    LOWEST_CALORIES = ("Lowest calories", Nutrient.CALORIES, "LOW")
    LOWEST_SODIUM = ("Lowest sodium", Nutrient.SODIUM, "LOW")
    LOWEST_FAT = ("Lowest fat", Nutrient.FAT, "LOW")
    HIGHEST_PROTEIN = ("Highest protein", Nutrient.PROTEIN, "HIGH")
    HIGHEST_FIBRE = ("Highest fibre", Nutrient.FIBRE, "HIGH")

    def __init__(self, label: str, nutrient: Nutrient | None, order: str | None):
        self._label = label
        self._nutrient = nutrient
        self._order = order

    @property
    def label(self) -> str:
        return self._label

    @property
    def nutrient(self) -> Nutrient | None:
        return self._nutrient

    @property
    def order(self) -> str | None:
        return self._order


class RecommendationOptions:
    """What the user chose: a focus and an optional product category."""

    ANY_CATEGORY = "Any"

    def __init__(self, focuses: list[RecommendationFocus] | None = None,
                 categories: list[str] | None = None):
        """Several focuses and categories can be picked. No category means any category."""
        chosen = []
        for focus in focuses or [RecommendationFocus.BEST_MATCH]:
            if focus not in chosen:
                chosen.append(focus)
        self._focuses = tuple(chosen)
        names = []
        for name in categories or []:
            name = name.strip()
            if name and name != self.ANY_CATEGORY and name.casefold() not in [n.casefold() for n in names]:
                names.append(name)
        self._categories = tuple(names)

    @property
    def focuses(self) -> tuple[RecommendationFocus, ...]:
        return self._focuses

    @property
    def categories(self) -> tuple[str, ...]:
        return self._categories

    def nutrient_focuses(self) -> list[RecommendationFocus]:
        """Focuses that rank by one nutrient (everything except 'best match')."""
        return [focus for focus in self._focuses if focus.nutrient is not None]

    def includes_best_match(self) -> bool:
        return RecommendationFocus.BEST_MATCH in self._focuses

    def describe_focus(self) -> str:
        return " + ".join(focus.label for focus in self._focuses)

    def describe_categories(self) -> str:
        return ", ".join(self._categories) if self._categories else self.ANY_CATEGORY

    def matches_category(self, product: Product) -> bool:
        if not self._categories:
            return True
        return (product.category or "").casefold() in [name.casefold() for name in self._categories]

    def cache_key(self) -> tuple:
        return (tuple(sorted(focus.name for focus in self._focuses)),
                tuple(sorted(name.casefold() for name in self._categories)))


class ScoredProduct:
    """A product with its score against one user's goals."""

    def __init__(self, product: Product, score: float, goal_results: list[GoalResult]):
        self._product = product
        self._score = round(float(score), 1)
        self._goal_results = tuple(goal_results)

    @property
    def product(self) -> Product:
        return self._product

    @property
    def score(self) -> float:
        return self._score

    @property
    def goal_results(self) -> tuple[GoalResult, ...]:
        return self._goal_results


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
