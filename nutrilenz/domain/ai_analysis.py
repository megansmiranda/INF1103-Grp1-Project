from .product_suggestion import ProductSuggestion


class AIAnalysis:
    """The validated AI answer for one product. Read-only after creation."""

    FIELDS = ("relevant_ingredients", "goal_alignment", "claim_status", "evidence",
              "explanation", "confidence", "suggestions", "suggested_products")

    def __init__(self, relevant_ingredients: list[str], goal_alignment: str, claim_status: str,
                 evidence: list[str], explanation: str, confidence: str, suggestions: list[str],
                 suggested_products: list[ProductSuggestion] | None = None):
        self._relevant_ingredients = tuple(relevant_ingredients)
        self._goal_alignment = goal_alignment
        self._claim_status = claim_status
        self._evidence = tuple(evidence)
        self._explanation = explanation
        self._confidence = confidence
        self._suggestions = tuple(suggestions)
        self._suggested_products = tuple(suggested_products or [])

    @property
    def relevant_ingredients(self) -> tuple[str, ...]:
        return self._relevant_ingredients

    @property
    def goal_alignment(self) -> str:
        return self._goal_alignment

    @property
    def claim_status(self) -> str:
        return self._claim_status

    @property
    def evidence(self) -> tuple[str, ...]:
        return self._evidence

    @property
    def explanation(self) -> str:
        return self._explanation

    @property
    def confidence(self) -> str:
        return self._confidence

    @property
    def suggestions(self) -> tuple[str, ...]:
        return self._suggestions

    @property
    def suggested_products(self) -> tuple[ProductSuggestion, ...]:
        return self._suggested_products

    def to_dict(self) -> dict:
        return {
            "relevant_ingredients": list(self._relevant_ingredients),
            "goal_alignment": self._goal_alignment,
            "claim_status": self._claim_status,
            "evidence": list(self._evidence),
            "explanation": self._explanation,
            "confidence": self._confidence,
            "suggestions": list(self._suggestions),
            "suggested_products": [p.to_dict() for p in self._suggested_products],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AIAnalysis":
        return cls(data["relevant_ingredients"], data["goal_alignment"], data["claim_status"],
                   data["evidence"], data["explanation"], data["confidence"],
                   data.get("suggestions", []),
                   [ProductSuggestion.from_dict(p) for p in data.get("suggested_products", [])])
