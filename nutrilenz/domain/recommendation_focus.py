from enum import Enum

from .nutrients import Nutrient


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
