from ..domain.product_suggestion import ProductSuggestion


class RecommendationAdvice:
    """AI reasons for each shortlisted product, general tips and other Singapore products."""

    def __init__(self, reasons: dict[int, str], tips: list[str],
                 suggested_products: list[ProductSuggestion] | None = None):
        self._reasons = dict(reasons)
        self._tips = list(tips)
        self._suggested_products = list(suggested_products or [])

    @property
    def suggested_products(self) -> list[ProductSuggestion]:
        return list(self._suggested_products)

    @property
    def reasons(self) -> dict[int, str]:
        return dict(self._reasons)

    @property
    def tips(self) -> list[str]:
        return list(self._tips)
