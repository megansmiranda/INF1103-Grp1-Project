from ..domain.ai_analysis import AIAnalysis
from ..domain.goal_result import GoalResult
from ..domain.target_status import TargetStatus
from ..domain.dietary_report import DietaryReport
from ..domain.product import Product


class EvaluationContext:
    """Everything a rule may look at for one product. Read-only."""

    def __init__(self, product: Product, ai: AIAnalysis, goal_results: list[GoalResult],
                 dietary_report: DietaryReport | None = None):
        self._product = product
        self._ai = ai
        self._goal_results = tuple(goal_results)
        self._dietary_report = dietary_report or DietaryReport()

    @property
    def dietary_report(self) -> DietaryReport:
        return self._dietary_report

    @property
    def product(self) -> Product:
        return self._product

    @property
    def ai(self) -> AIAnalysis:
        return self._ai

    @property
    def goal_results(self) -> tuple[GoalResult, ...]:
        return self._goal_results

    def any_goal(self, status: TargetStatus) -> bool:
        return any(result.status is status for result in self._goal_results)

    def all_goals_met(self) -> bool:
        return bool(self._goal_results) and all(
            result.status is TargetStatus.MET for result in self._goal_results)
