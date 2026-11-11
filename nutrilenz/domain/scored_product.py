from .goal_result import GoalResult
from .dietary_report import DietaryReport
from .product import Product


class ScoredProduct:
    """A product with its score against one user's goals."""

    def __init__(self, product: Product, score: float, goal_results: list[GoalResult],
                 dietary_report: DietaryReport | None = None):
        self._product = product
        self._score = round(float(score), 1)
        self._goal_results = tuple(goal_results)
        self._dietary_report = dietary_report or DietaryReport()

    @property
    def dietary_report(self) -> DietaryReport:
        return self._dietary_report

    @property
    def ingredients_unknown(self) -> bool:
        return not self._product.ingredient_text.strip()

    @property
    def product(self) -> Product:
        return self._product

    @property
    def score(self) -> float:
        return self._score

    @property
    def goal_results(self) -> tuple[GoalResult, ...]:
        return self._goal_results
