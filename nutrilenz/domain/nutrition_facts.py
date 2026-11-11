from .nutrients import Nutrient
from .amount import Amount


class NutritionFacts:
    """Per-serving nutrition values from one label.
    A nutrient that is None or not listed means 'not on the label', never zero."""

    def __init__(self, values: dict[Nutrient, float | None]):
        self._values: dict[Nutrient, float | None] = {}
        for nutrient, value in values.items():
            if value is not None and (not Amount.is_number(value) or value < 0):
                raise ValueError(nutrient.label + " must be a non-negative number or blank")
            self._values[nutrient] = None if value is None else float(value)

    def get(self, nutrient: Nutrient) -> float | None:
        return self._values.get(nutrient)

    def is_supplied(self, nutrient: Nutrient) -> bool:
        return self._values.get(nutrient) is not None

    def supplied(self) -> dict[Nutrient, float]:
        return {n: v for n, v in self._values.items() if v is not None}

    def to_dict(self) -> dict[str, float | None]:
        """Every known nutrient key, None when not on the label (JSON null)."""
        return {n.key: self._values.get(n) for n in Nutrient}

    @classmethod
    def from_dict(cls, data: dict) -> "NutritionFacts":
        return cls({Nutrient.from_key(key): value for key, value in data.items()})
