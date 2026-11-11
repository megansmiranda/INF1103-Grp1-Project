from .vegetarian_check import VegetarianCheck


class VeganCheck(VegetarianCheck):
    key = "vegan"
    label = "Vegan"

    @property
    def keyword_groups(self) -> tuple[str, ...]:
        return super().keyword_groups + ("dairy", "egg", "other_animal")
