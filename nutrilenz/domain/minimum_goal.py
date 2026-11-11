from .goal import Goal


class MinimumGoal(Goal):
    """Reach at least the target, e.g. high protein. Equal counts as met."""

    @property
    def direction(self) -> str:
        return "MIN"

    def _is_met(self, value: float) -> bool:
        return value >= self._target

    def closeness(self, value: float) -> float:
        return min(1.0, value / self._target)

    def describe(self) -> str:
        return self._nutrient.label + " at least " + self._amount() + " per serving"
