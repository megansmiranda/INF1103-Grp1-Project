from abc import ABC, abstractmethod

from .nutrients import Nutrient
from .amount import Amount
from .nutrition_facts import NutritionFacts
from .target_status import TargetStatus


class Goal(ABC):
    """A nutrition goal with a per-serving target.
    evaluate() is the same for every goal; subclasses only decide what 'met' means."""

    def __init__(self, nutrient: Nutrient, target: float):
        if not Amount.is_number(target) or target <= 0:
            raise ValueError(nutrient.label + " target must be a positive number")
        self._nutrient = nutrient
        self._target = float(target)

    @property
    def nutrient(self) -> Nutrient:
        return self._nutrient

    @property
    def target(self) -> float:
        return self._target

    @property
    @abstractmethod
    def direction(self) -> str:
        """'MAX' (stay at or under the target) or 'MIN' (reach at least the target)."""

    @abstractmethod
    def _is_met(self, value: float) -> bool:
        """True when the label value satisfies this goal."""

    @abstractmethod
    def closeness(self, value: float) -> float:
        """0.0 to 1.0, how close the value is to meeting the goal. Used for ranking."""

    @abstractmethod
    def describe(self) -> str:
        """Short text such as 'Sugar at most 10 g per serving'."""

    def evaluate(self, nutrition: NutritionFacts) -> TargetStatus:
        value = nutrition.get(self._nutrient)
        if value is None:
            return TargetStatus.MISSING
        return TargetStatus.MET if self._is_met(value) else TargetStatus.MISMATCH

    def _amount(self) -> str:
        return f"{self._target:g} {self._nutrient.unit}"

    def to_dict(self) -> dict:
        return {"nutrient": self._nutrient.key, "direction": self.direction, "target": self._target}
