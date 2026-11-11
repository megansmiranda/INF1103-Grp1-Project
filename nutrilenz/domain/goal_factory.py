from .nutrients import Nutrient
from .goal import Goal
from .limit_goal import LimitGoal
from .minimum_goal import MinimumGoal


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
