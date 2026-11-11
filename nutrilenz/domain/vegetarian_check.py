from .dietary_check import DietaryCheck


class VegetarianCheck(DietaryCheck):
    key = "vegetarian"
    label = "Vegetarian — dairy allowed"

    @property
    def keyword_groups(self) -> tuple[str, ...]:
        return ("meat", "animal_fats", "fish", "shellfish", "hidden_animal")
