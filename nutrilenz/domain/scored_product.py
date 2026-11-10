from .goal_result import GoalResult
from .product import Product


class ScoredProduct:
    """A product with its score against one user's goals."""

    def __init__(self, product: Product, score: float, goal_results: list[GoalResult]):
        self._product = product
        self._score = round(float(score), 1)
        self._goal_results = tuple(goal_results)

    @property
    def product(self) -> Product:
        return self._product

    @property
    def score(self) -> float:
        return self._score

    @property
    def goal_results(self) -> tuple[GoalResult, ...]:
        return self._goal_results
