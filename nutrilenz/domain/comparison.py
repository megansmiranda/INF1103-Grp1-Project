from datetime import datetime

from .scored_product import ScoredProduct


class Comparison:
    """Products picked up together on a shelf, ranked best fit first, with the AI's
    explanation. Logic decides the order; the AI only explains it."""

    def __init__(self, user_id: int, ranked: list[ScoredProduct], summary: str,
                 strengths: dict[int, str], drawbacks: dict[int, str], provider: str,
                 avoid_matches: dict[int, list[str]] | None = None,
                 compared_at: datetime | None = None):
        if len(ranked) < 2:
            raise ValueError("A comparison needs at least two products")
        self._user_id = user_id
        self._ranked = tuple(ranked)
        self._summary = summary
        self._strengths = dict(strengths)
        self._drawbacks = dict(drawbacks)
        self._provider = provider
        # Saved with the result, so later profile edits do not change this comparison
        self._avoid_matches = {rank: tuple(words) for rank, words in (avoid_matches or {}).items()}
        self._compared_at = compared_at or datetime.now()

    @property
    def user_id(self) -> int:
        return self._user_id

    @property
    def ranked(self) -> tuple[ScoredProduct, ...]:
        return self._ranked

    @property
    def winner(self) -> ScoredProduct:
        return self._ranked[0]

    def is_clean(self, rank: int) -> bool:
        """No possible dietary concern and no avoided ingredient (rank is 1-based)."""
        item = self._ranked[rank - 1]
        return not item.dietary_report.has_concern and not self.avoid_matches(rank)

    @property
    def winner_is_clean(self) -> bool:
        return self.is_clean(1)

    @property
    def is_close_call(self) -> bool:
        """True when the top two are both clean and their scores are within 5 points."""
        first, second = self._ranked[0], self._ranked[1]
        return abs(first.score - second.score) <= 5 and self.is_clean(1) and self.is_clean(2)

    @property
    def summary(self) -> str:
        return self._summary

    def strength(self, rank: int) -> str:
        return self._strengths.get(rank, "")

    def drawback(self, rank: int) -> str:
        return self._drawbacks.get(rank, "")

    def avoid_matches(self, rank: int) -> tuple[str, ...]:
        return self._avoid_matches.get(rank, ())

    def goal_rows(self) -> list[tuple[str, list]]:
        """One row per goal: the goal text and each product's result, in ranked order."""
        first = self._ranked[0].goal_results
        return [(result.description, [item.goal_results[i] for item in self._ranked])
                for i, result in enumerate(first)]

    @property
    def provider(self) -> str:
        return self._provider

    @property
    def compared_at(self) -> datetime:
        return self._compared_at
