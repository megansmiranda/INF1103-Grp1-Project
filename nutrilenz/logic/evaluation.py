from ..domain.flag import Flag
from ..domain.goal_result import GoalResult
from ..domain.dietary_report import DietaryReport


class Evaluation:
    """Result of applying the rules to one product."""

    def __init__(self, flags: list[Flag], goal_results: list[GoalResult], score: float,
                 dietary_report: DietaryReport | None = None):
        self._flags = tuple(flags)
        self._goal_results = tuple(goal_results)
        self._score = score
        self._dietary_report = dietary_report or DietaryReport()

    @property
    def dietary_report(self) -> DietaryReport:
        return self._dietary_report

    @property
    def flags(self) -> tuple[Flag, ...]:
        return self._flags

    @property
    def goal_results(self) -> tuple[GoalResult, ...]:
        return self._goal_results

    @property
    def score(self) -> float:
        return self._score
