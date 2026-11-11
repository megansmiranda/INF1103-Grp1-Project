from datetime import datetime

from .dietary_report import DietaryReport
from .product import Product
from .flag import Flag
from .ai_analysis import AIAnalysis
from .goal_result import GoalResult


class Analysis:
    """One saved analysis record.
    Owns its AIAnalysis and goal results (created and deleted with it).
    Refers to a Product and a user that both exist on their own (association)."""

    def __init__(self, user_id: int, product: Product, profile_snapshot: dict,
                 ai_analysis: AIAnalysis, flags: list[Flag], goal_results: list[GoalResult],
                 score: float, provider: str, analysed_at: datetime | None = None,
                 analysis_id: int | None = None, dietary_report: DietaryReport | None = None):
        self._user_id = user_id
        self._product = product
        self._profile_snapshot = dict(profile_snapshot)
        self._ai_analysis = ai_analysis
        self._flags = tuple(flags)
        self._goal_results = tuple(goal_results)
        self._dietary_report = dietary_report or DietaryReport()
        self._score = round(float(score), 1)
        self._provider = provider
        self._analysed_at = analysed_at or datetime.now().replace(microsecond=0)
        self._analysis_id = analysis_id

    @property
    def analysis_id(self) -> int | None:
        return self._analysis_id

    def assign_id(self, analysis_id: int) -> None:
        if self._analysis_id is not None and self._analysis_id != analysis_id:
            raise ValueError("Analysis already has an id")
        self._analysis_id = analysis_id

    @property
    def user_id(self) -> int:
        return self._user_id

    @property
    def product(self) -> Product:
        return self._product

    @property
    def profile_snapshot(self) -> dict:
        return dict(self._profile_snapshot)

    @property
    def ai_analysis(self) -> AIAnalysis:
        return self._ai_analysis

    @property
    def flags(self) -> tuple[Flag, ...]:
        return self._flags

    @property
    def goal_results(self) -> tuple[GoalResult, ...]:
        return self._goal_results

    @property
    def dietary_report(self) -> DietaryReport:
        return self._dietary_report

    @property
    def score(self) -> float:
        return self._score

    @property
    def provider(self) -> str:
        return self._provider

    @property
    def analysed_at(self) -> datetime:
        return self._analysed_at

    def has_flag(self, flag: Flag) -> bool:
        return flag in self._flags

    def flag_names(self) -> list[str]:
        return [flag.value for flag in self._flags]
