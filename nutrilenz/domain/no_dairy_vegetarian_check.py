from .vegetarian_check import VegetarianCheck


class NoDairyVegetarianCheck(VegetarianCheck):
    key = "vegetarian_no_dairy"
    label = "Vegetarian — no dairy"

    @property
    def keyword_groups(self) -> tuple[str, ...]:
        return super().keyword_groups + ("dairy",)
