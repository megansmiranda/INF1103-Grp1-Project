from .nutrition_facts import NutritionFacts


class Product:
    """One packaged food product. Products are shared: many analyses and
    recommendations can point at the same product."""

    def __init__(self, name: str, nutrition: NutritionFacts, ingredient_text: str,
                 brand: str | None = None, category: str | None = None,
                 marketing_claim: str | None = None, product_id: int | None = None):
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Product name is required")
        if not isinstance(ingredient_text, str):
            raise ValueError("Ingredient list must be text (blank if not on the label)")
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
