from .goal import Goal
from .target_status import TargetStatus
from .product import Product


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
