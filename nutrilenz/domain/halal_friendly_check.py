from .dietary_check import DietaryCheck


class HalalFriendlyCheck(DietaryCheck):
    key = "halal_friendly"
    label = "Halal-friendly"

    @property
    def keyword_groups(self) -> tuple[str, ...]:
        return ("halal_pork", "halal_gelatine", "alcohol")
