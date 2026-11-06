from abc import ABC, abstractmethod
from enum import Enum

from .nutrients import Nutrient
from .product import Amount, NutritionFacts


class TargetStatus(Enum):
    MET = "MET"
    MISMATCH = "MISMATCH"
    MISSING = "MISSING"          # nutrient not on the label, so it cannot be compared


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


class LimitGoal(Goal):
    """Stay at or below the target, e.g. reduce sugar. Equal counts as met."""

    @property
    def direction(self) -> str:
        return "MAX"

    def _is_met(self, value: float) -> bool:
        return value <= self._target

    def closeness(self, value: float) -> float:
        if value <= self._target:
            return 1.0
        return max(0.0, 1.0 - (value - self._target) / self._target)

    def describe(self) -> str:
        return self._nutrient.label + " at most " + self._amount() + " per serving"


class MinimumGoal(Goal):
    """Reach at least the target, e.g. high protein. Equal counts as met."""

    @property
    def direction(self) -> str:
        return "MIN"

    def _is_met(self, value: float) -> bool:
        return value >= self._target

    def closeness(self, value: float) -> float:
        return min(1.0, value / self._target)

    def describe(self) -> str:
        return self._nutrient.label + " at least " + self._amount() + " per serving"


class GoalFactory:
    """Builds the right Goal subclass from saved data or a preset name."""

    _TYPES = {"MAX": LimitGoal, "MIN": MinimumGoal}

    # Friendly presets shown in the profile form. The first three are the Part 1 goals.
    PRESETS = {
        "REDUCE_SUGAR": (Nutrient.SUGAR, "MAX"),
        "HIGH_PROTEIN": (Nutrient.PROTEIN, "MIN"),
        "LOWER_SODIUM": (Nutrient.SODIUM, "MAX"),
        "LOW_CALORIES": (Nutrient.CALORIES, "MAX"),
        "LOW_FAT": (Nutrient.FAT, "MAX"),
        "LOW_SATURATED_FAT": (Nutrient.SATURATED_FAT, "MAX"),
        "LOW_CARB": (Nutrient.CARBOHYDRATE, "MAX"),
        "HIGH_FIBRE": (Nutrient.FIBRE, "MIN"),
    }

    @classmethod
    def create(cls, nutrient_key: str, direction: str, target: float) -> Goal:
        if direction not in cls._TYPES:
            raise ValueError("Direction must be MAX or MIN")
        return cls._TYPES[direction](Nutrient.from_key(nutrient_key), target)

    @classmethod
    def from_preset(cls, preset: str, target: float) -> Goal:
        if preset not in cls.PRESETS:
            raise ValueError("Unknown goal: " + str(preset))
        nutrient, direction = cls.PRESETS[preset]
        return cls._TYPES[direction](nutrient, target)

    @classmethod
    def from_dict(cls, data: dict) -> Goal:
        return cls.create(data["nutrient"], data["direction"], data["target"])

    @classmethod
    def preset_name(cls, goal: Goal) -> str | None:
        for name, (nutrient, direction) in cls.PRESETS.items():
            if nutrient is goal.nutrient and direction == goal.direction:
                return name
        return None
