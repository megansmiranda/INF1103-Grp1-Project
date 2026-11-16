class ComparisonAdvice:
    """What the AI says about a ranked set of products: one summary, plus one
    strength and one drawback for each product (keyed by its 1-based rank)."""

    def __init__(self, summary: str, strengths: dict[int, str], drawbacks: dict[int, str]):
        self._summary = summary
        self._strengths = dict(strengths)
        self._drawbacks = dict(drawbacks)

    @property
    def summary(self) -> str:
        return self._summary

    def strength(self, rank: int) -> str:
        return self._strengths.get(rank, "")

    def drawback(self, rank: int) -> str:
        return self._drawbacks.get(rank, "")
