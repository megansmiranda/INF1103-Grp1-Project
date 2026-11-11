from .dietary_check import DietaryCheck
from .vegetarian_check import VegetarianCheck
from .no_dairy_vegetarian_check import NoDairyVegetarianCheck
from .vegan_check import VeganCheck
from .halal_friendly_check import HalalFriendlyCheck
from .allergen_check import AllergenCheck


class DietaryCheckFactory:
    # Increasing strictness: each later diet includes all earlier diet keywords.
    DIETS = ("vegetarian", "vegetarian_no_dairy", "vegan")
    TYPES = {"vegetarian": (VegetarianCheck, ()), "vegetarian_no_dairy": (NoDairyVegetarianCheck, ()),
             "vegan": (VeganCheck, ()), "halal_friendly": (HalalFriendlyCheck, ()),
             **{key: (AllergenCheck, (key,)) for key in AllergenCheck.LABELS}}

    @classmethod
    def create(cls, key: str) -> DietaryCheck:
        if key not in cls.TYPES:
            raise ValueError("Unknown dietary check: " + str(key))
        check_type, args = cls.TYPES[key]
        return check_type(*args)

    @classmethod
    def options(cls) -> tuple[DietaryCheck, ...]:
        return tuple(cls.create(key) for key in cls.TYPES)

    @classmethod
    def from_keys(cls, keys: list[str]) -> tuple[DietaryCheck, ...]:
        checks = tuple(cls.create(key) for key in dict.fromkeys(keys))
        if len(set(keys).intersection(cls.DIETS)) > 1:
            raise ValueError("Choose only one diet.")
        return checks

    @classmethod
    def normalise_saved_keys(cls, keys: list[str]) -> list[str]:
        """Read legacy preferences using the strictest diet, preserving other checks."""
        diets = [key for key in cls.DIETS if key in keys]
        if len(diets) < 2:
            return list(keys)
        return [key for key in keys if key not in cls.DIETS or key == diets[-1]]
