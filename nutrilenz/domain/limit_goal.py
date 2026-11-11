from .goal import Goal


class LimitGoal(Goal):
    """Stay at or below the target, e.g. reduce sugar. Equal counts as met."""

    @property
    def direction(self) -> str:
        return "MAX"

    def _is_met(self, value: float) -> bool:
        return value <= self._target

    def closeness(self, value: float) -> float:
        if value <= self._target:
            return 1.0
        return max(0.0, 1.0 - (value - self._target) / self._target)

    def describe(self) -> str:
        return self._nutrient.label + " at most " + self._amount() + " per serving"
