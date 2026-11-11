from ..domain.flag import Flag
from ..domain.target_status import TargetStatus
from .evaluation_context import EvaluationContext
from .rule import Rule


class GoalMismatchRule(Rule):
    """Any goal clearly not met by the label numbers."""

    @property
    def flag(self) -> Flag:
        return Flag.GOAL_MISMATCH

    def applies(self, context: EvaluationContext, flags_so_far: list[Flag]) -> bool:
        return context.any_goal(TargetStatus.MISMATCH)
