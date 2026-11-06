import math

from .nutrients import Nutrient


class Amount:
    """Checks for nutrient amounts and targets."""

    @staticmethod
    def is_number(value: object) -> bool:
        """Finite int/float only. bool and numeric text are rejected."""
        if isinstance(value, bool):
            return False
        return isinstance(value, int) or (isinstance(value, float) and math.isfinite(value))


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


class Product:
    """One packaged food product. Products are shared: many analyses and
    recommendations can point at the same product."""

    def __init__(self, name: str, nutrition: NutritionFacts, ingredient_text: str,
                 brand: str | None = None, category: str | None = None,
                 marketing_claim: str | None = None, product_id: int | None = None):
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Product name is required")
        if not isinstance(ingredient_text, str) or not ingredient_text.strip():
            raise ValueError("Ingredient list is required")
        self._name = name.strip()
        self._nutrition = nutrition
        self._ingredient_text = ingredient_text.strip()
        self._brand = self._clean(brand)
        self._category = self._clean(category)
        self._marketing_claim = self._clean(marketing_claim)
        self._product_id = product_id

    @staticmethod
    def _clean(text: str | None) -> str | None:
        return text.strip() if isinstance(text, str) and text.strip() else None

    @property
    def product_id(self) -> int | None:
        return self._product_id

    def assign_id(self, product_id: int) -> None:
        """Set by the Data Manager once the product is stored. Only allowed once."""
        if self._product_id is not None and self._product_id != product_id:
            raise ValueError("Product already has an id")
        self._product_id = product_id

    @property
    def name(self) -> str:
        return self._name

    @property
    def brand(self) -> str | None:
        return self._brand

    @property
    def category(self) -> str | None:
        return self._category

    @property
    def nutrition(self) -> NutritionFacts:
        return self._nutrition

    @property
    def ingredient_text(self) -> str:
        return self._ingredient_text

    @property
    def marketing_claim(self) -> str | None:
        return self._marketing_claim

    @property
    def has_claim(self) -> bool:
        return self._marketing_claim is not None

    def display_name(self) -> str:
        return self._name + (" (" + self._brand + ")" if self._brand else "")

    def ingredients_found(self, words: list[str]) -> list[str]:
        """Which of the given words appear in the ingredient list (case ignored)."""
        text = self._ingredient_text.casefold()
        return [word for word in words if word.strip() and word.strip().casefold() in text]

    def to_dict(self) -> dict:
        return {
            "product_id": self._product_id,
            "product_name": self._name,
            "brand": self._brand,
            "category": self._category,
            "nutrition": self._nutrition.to_dict(),
            "ingredient_text": self._ingredient_text,
            "marketing_claim": self._marketing_claim,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Product":
        return cls(name=data["product_name"],
                   nutrition=NutritionFacts.from_dict(data.get("nutrition") or {}),
                   ingredient_text=data["ingredient_text"],
                   brand=data.get("brand"),
                   category=data.get("category"),
                   marketing_claim=data.get("marketing_claim"),
                   product_id=data.get("product_id"))
