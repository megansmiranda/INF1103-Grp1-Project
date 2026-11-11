import json
import threading

from ..domain.recommendation import Recommendation
from ..domain.recommendation_options import RecommendationOptions
from ..domain.user import User


class RecommendationCache:
    """Remembers recent recommendations so asking the same thing twice costs no AI call.
    A change to goals, dietary checks or the product catalogue gives a new key."""

    MAX_ENTRIES = 100

    def __init__(self):
        self._entries: dict[tuple, Recommendation] = {}
        self._lock = threading.Lock()

    @staticmethod
    def key(user: User, options: RecommendationOptions, product_ids: list[int]) -> tuple:
        profile = json.dumps(user.profile.snapshot(), sort_keys=True)
        return user.user_id, profile, options.cache_key(), tuple(sorted(product_ids))

    def get(self, key: tuple) -> Recommendation | None:
        with self._lock:
            return self._entries.get(key)

    def put(self, key: tuple, recommendation: Recommendation) -> None:
        with self._lock:
            if len(self._entries) >= self.MAX_ENTRIES:
                self._entries.pop(next(iter(self._entries)))      # drop the oldest
            self._entries[key] = recommendation
