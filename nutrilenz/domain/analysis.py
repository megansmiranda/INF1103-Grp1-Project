from datetime import datetime
from enum import Enum

from .goals import Goal, TargetStatus
from .product import Product


class Flag(Enum):
    GOAL_MISMATCH = "GOAL_MISMATCH"
    CLAIM_REVIEW = "CLAIM_REVIEW"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    GOOD_MATCH = "GOOD_MATCH"


class ProductSuggestion:
    """A real product the AI suggests buying in Singapore. Not checked against any
    shop, so it is always shown as an AI suggestion."""

    def __init__(self, name: str, brand: str | None, reason: str):
        self._name = name
        self._brand = brand
        self._reason = reason

    @property
    def name(self) -> str:
        return self._name

    @property
    def brand(self) -> str | None:
        return self._brand

    @property
    def reason(self) -> str:
        return self._reason

    def display_name(self) -> str:
        if self._brand and self._brand.casefold() not in self._name.casefold():
            return self._brand + " " + self._name
        return self._name

    def to_dict(self) -> dict:
        return {"name": self._name, "brand": self._brand, "reason": self._reason}

    @classmethod
    def from_dict(cls, data: dict) -> "ProductSuggestion":
        return cls(data["name"], data.get("brand"), data["reason"])


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


class GoalResult:
    """How one goal turned out for one product."""

    def __init__(self, description: str, status: TargetStatus, value: float | None, unit: str):
        self._description = description
        self._status = status
        self._value = value
        self._unit = unit

    @classmethod
    def for_goal(cls, goal: Goal, product: Product) -> "GoalResult":
        return cls(goal.describe(), goal.evaluate(product.nutrition),
                   product.nutrition.get(goal.nutrient), goal.nutrient.unit)

    @property
    def description(self) -> str:
        return self._description

    @property
    def status(self) -> TargetStatus:
        return self._status

    @property
    def value(self) -> float | None:
        return self._value

    def value_text(self) -> str:
        return "not on label" if self._value is None else f"{self._value:g} {self._unit}"

    def to_dict(self) -> dict:
        return {"description": self._description, "status": self._status.value,
                "value": self._value, "unit": self._unit}

    @classmethod
    def from_dict(cls, data: dict) -> "GoalResult":
        return cls(data["description"], TargetStatus(data["status"]), data["value"], data["unit"])


class Analysis:
    """One saved analysis record.
    Owns its AIAnalysis and goal results (created and deleted with it).
    Refers to a Product and a user that both exist on their own (association)."""

    def __init__(self, user_id: int, product: Product, profile_snapshot: dict,
                 ai_analysis: AIAnalysis, flags: list[Flag], goal_results: list[GoalResult],
                 score: float, provider: str, analysed_at: datetime | None = None,
                 analysis_id: int | None = None):
        self._user_id = user_id
        self._product = product
        self._profile_snapshot = dict(profile_snapshot)
        self._ai_analysis = ai_analysis
        self._flags = tuple(flags)
        self._goal_results = tuple(goal_results)
        self._score = round(float(score), 1)
        self._provider = provider
        self._analysed_at = analysed_at or datetime.now().replace(microsecond=0)
        self._analysis_id = analysis_id

    @property
    def analysis_id(self) -> int | None:
        return self._analysis_id

    def assign_id(self, analysis_id: int) -> None:
        if self._analysis_id is not None and self._analysis_id != analysis_id:
            raise ValueError("Analysis already has an id")
        self._analysis_id = analysis_id

    @property
    def user_id(self) -> int:
        return self._user_id

    @property
    def product(self) -> Product:
        return self._product

    @property
    def profile_snapshot(self) -> dict:
        return dict(self._profile_snapshot)

    @property
    def ai_analysis(self) -> AIAnalysis:
        return self._ai_analysis

    @property
    def flags(self) -> tuple[Flag, ...]:
        return self._flags

    @property
    def goal_results(self) -> tuple[GoalResult, ...]:
        return self._goal_results

    @property
    def score(self) -> float:
        return self._score

    @property
    def provider(self) -> str:
        return self._provider

    @property
    def analysed_at(self) -> datetime:
        return self._analysed_at

    def has_flag(self, flag: Flag) -> bool:
        return flag in self._flags

    def flag_names(self) -> list[str]:
        return [flag.value for flag in self._flags]
