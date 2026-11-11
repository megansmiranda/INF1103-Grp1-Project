from ..domain.product_suggestion import ProductSuggestion
from ..domain.amount import Amount


class SchemaChecker:
    """Small checks used by every AI task. Bad values are rejected, never 'fixed'."""

    def exact_keys(self, data: dict, required: tuple[str, ...]) -> None:
        missing = [key for key in required if key not in data]
        extra = [key for key in data if key not in required]
        if missing:
            raise ValueError("Missing fields: " + ", ".join(missing))
        if extra:
            raise ValueError("Unexpected fields: " + ", ".join(extra))

    def string_list(self, data: dict, field: str, allow_empty: bool = True) -> list[str]:
        value = data[field]
        if not isinstance(value, list):
            raise ValueError(field + " must be a list")
        for item in value:
            if not isinstance(item, str) or not item.strip():
                raise ValueError(field + " must only contain non-empty text")
        if not allow_empty and not value:
            raise ValueError(field + " must not be empty")
        return [item.strip() for item in value]

    def choice(self, data: dict, field: str, allowed: tuple[str, ...]) -> str:
        if data[field] not in allowed:
            raise ValueError("Bad " + field + ": " + str(data[field]))
        return data[field]

    def text(self, data: dict, field: str, allow_null: bool = False) -> str | None:
        value = data[field]
        if value is None and allow_null:
            return None
        if not isinstance(value, str) or not value.strip():
            raise ValueError(field + " must be non-empty text")
        return value.strip()

    def amount_or_null(self, value: object, field: str) -> float | None:
        if value is None:
            return None
        if not Amount.is_number(value) or value < 0:
            raise ValueError(field + " must be a non-negative number or null")
        return float(value)

    def product_suggestions(self, data: dict, field: str, max_items: int = 3) -> list[ProductSuggestion]:
        """A list of {name, brand, reason} objects. [] is allowed (AI was not sure)."""
        value = data[field]
        if not isinstance(value, list):
            raise ValueError(field + " must be a list")
        if len(value) > max_items:
            raise ValueError(f"{field} must have at most {max_items} items")
        suggestions, seen = [], set()
        for item in value:
            if not isinstance(item, dict):
                raise ValueError("each item in " + field + " must be an object")
            self.exact_keys(item, ("name", "brand", "reason"))
            name = self.text(item, "name")
            if len(name) > 100:
                raise ValueError(field + " names must be short")
            if name.casefold() in seen:
                raise ValueError(field + " must not repeat a product")
            seen.add(name.casefold())
            suggestions.append(ProductSuggestion(name, self.text(item, "brand", allow_null=True),
                                                 self.text(item, "reason")))
        return suggestions

    def boolean(self, data: dict, field: str) -> bool:
        if not isinstance(data[field], bool):
            raise ValueError(field + " must be true or false")
        return data[field]
