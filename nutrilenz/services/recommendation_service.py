from ..ai.ai_manager import AIManager
from ..data.data_manager import DataManager
from ..domain.recommendation import Recommendation
from ..domain.recommendation_options import RecommendationOptions
from ..domain.user import User
from ..logic.logic_manager import LogicManager
from .job import Job
from .recommendation_cache import RecommendationCache


class RecommendationService:
    """Shortlists saved products with the Logic Manager, then asks the AI to explain
    the picks and give tips. The AI can only choose from the shortlist."""

    def __init__(self, ai: AIManager, logic: LogicManager, data: DataManager):
        self._ai = ai
        self._logic = logic
        self._data = data
        self._cache = RecommendationCache()

    def recommend(self, user: User, options: RecommendationOptions,
                  job: Job | None = None) -> Recommendation:
        if job:
            job.set_step("Ranking saved products against your goals")
        catalogue = self._data.catalogue()
        key = self._cache.key(user, options, [p.product_id for p in catalogue])
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        shortlist, excluded = self._logic.recommendation_candidates(catalogue, user.profile, options)
        if job:
            job.set_step("Asking the AI to explain the picks")
        advice = self._ai.advise(user.profile, options, shortlist)

        recommendation = Recommendation(user.user_id, options, excluded,
                                        tuple(check.label for check in user.profile.dietary_checks))
        for scored in shortlist:
            if scored.product.product_id in advice.reasons:
                recommendation.add(scored)
        for product_id, reason in advice.reasons.items():
            recommendation.set_reason(product_id, reason)
        recommendation.set_tips(advice.tips)
        recommendation.set_suggested_products(advice.suggested_products)
        self._cache.put(key, recommendation)
        return recommendation

    def categories(self) -> list[str]:
        return self._data.categories()
