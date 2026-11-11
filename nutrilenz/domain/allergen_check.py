from .dietary_check import DietaryCheck


class AllergenCheck(DietaryCheck):
    group = "allergen"
    LABELS = {"nuts": "Peanuts & tree nuts", "dairy": "Milk & dairy", "gluten": "Gluten",
              "egg": "Egg", "soy": "Soy", "shellfish": "Shellfish"}

    def __init__(self, allergen: str):
        if allergen not in self.LABELS:
            raise ValueError("Unknown allergen: " + str(allergen))
        self._allergen = allergen

    @property
    def key(self) -> str:
        return self._allergen

    @property
    def label(self) -> str:
        return self.LABELS[self._allergen]

    @property
    def keyword_groups(self) -> tuple[str, ...]:
        return (self._allergen,)
