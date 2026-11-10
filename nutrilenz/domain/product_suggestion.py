class ProductSuggestion:
    """A real product the AI suggests buying in Singapore. Not checked against any
    shop, so it is always shown as an AI suggestion."""

    def __init__(self, name: str, brand: str | None, reason: str):
        self._name = name
        self._brand = brand
        self._reason = reason

    @property
    def name(self) -> str:
        return self._name

    @property
    def brand(self) -> str | None:
        return self._brand

    @property
    def reason(self) -> str:
        return self._reason

    def display_name(self) -> str:
        if self._brand and self._brand.casefold() not in self._name.casefold():
            return self._brand + " " + self._name
        return self._name

    def to_dict(self) -> dict:
        return {"name": self._name, "brand": self._brand, "reason": self._reason}

    @classmethod
    def from_dict(cls, data: dict) -> "ProductSuggestion":
        return cls(data["name"], data.get("brand"), data["reason"])
