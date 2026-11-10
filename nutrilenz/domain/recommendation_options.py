from .product import Product
from .recommendation_focus import RecommendationFocus


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
