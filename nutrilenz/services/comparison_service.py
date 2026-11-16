from ..ai.ai_manager import AIManager
from ..domain.comparison import Comparison
from ..domain.product import Product
from ..domain.user import User
from ..logic.logic_manager import LogicManager
from .job import Job


class ComparisonService:
    """Shelf Compare: Logic ranks the products against the user's goals, then the AI
    explains the ranking in one call. Comparisons are shown, not saved."""

    MIN_PRODUCTS = 2
    MAX_PRODUCTS = 4

    def __init__(self, ai: AIManager, logic: LogicManager):
        self._ai = ai
        self._logic = logic

    def compare(self, user: User, products: list[Product], job: Job | None = None) -> Comparison:
        if not self.MIN_PRODUCTS <= len(products) <= self.MAX_PRODUCTS:
            raise ValueError(f"Compare {self.MIN_PRODUCTS} to {self.MAX_PRODUCTS} products")
        if job:
            job.set_step("Ranking the products against your goals")
        ranked = self._logic.compare(products, user.profile)
        if job:
            job.set_step("Asking the AI to explain the result")
        result = self._ai.compare(user.profile, ranked)
        advice = result.value
        ranks = range(1, len(ranked) + 1)
        avoid = list(user.profile.avoid_ingredients)
        return Comparison(user.user_id, ranked, advice.summary,
                          {rank: advice.strength(rank) for rank in ranks},
                          {rank: advice.drawback(rank) for rank in ranks}, result.provider,
                          {rank: ranked[rank - 1].product.ingredients_found(avoid) for rank in ranks})
