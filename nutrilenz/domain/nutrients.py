from enum import Enum


class Nutrient(Enum):
    """Nutrients the app understands. Adding one here makes it usable in goals,
    forms, the AI prompt and the database without changing any other class."""

    SUGAR = ("sugar_g", "Sugar", "g")
    PROTEIN = ("protein_g", "Protein", "g")
    SODIUM = ("sodium_mg", "Sodium", "mg")
    CALORIES = ("calories_kcal", "Calories", "kcal")
    FAT = ("fat_g", "Total fat", "g")
    SATURATED_FAT = ("saturated_fat_g", "Saturated fat", "g")
    CARBOHYDRATE = ("carbohydrate_g", "Carbohydrate", "g")
    FIBRE = ("fibre_g", "Dietary fibre", "g")

    def __init__(self, key: str, label: str, unit: str):
        self._key = key
        self._label = label
        self._unit = unit

    @property
    def key(self) -> str:
        return self._key

    @property
    def label(self) -> str:
        return self._label

    @property
    def unit(self) -> str:
        return self._unit

    @classmethod
    def from_key(cls, key: str) -> "Nutrient":
        for nutrient in cls:
            if nutrient.key == key:
                return nutrient
        raise ValueError("Unknown nutrient: " + str(key))

    @classmethod
    def keys(cls) -> list[str]:
        return [nutrient.key for nutrient in cls]
