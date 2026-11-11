from ..domain.flag import Flag
from ..domain.target_status import TargetStatus
from .evaluation_context import EvaluationContext
from .rule import Rule


class ManualReviewRule(Rule):
    """Missing label numbers or unsure AI output means a person should check it."""

    @property
    def flag(self) -> Flag:
        return Flag.MANUAL_REVIEW

    def applies(self, context: EvaluationContext, flags_so_far: list[Flag]) -> bool:
        ai = context.ai
        return (context.any_goal(TargetStatus.MISSING)
                or ai.confidence == "LOW"
                or ai.goal_alignment == "INSUFFICIENT_INFORMATION"
                or ai.claim_status == "INSUFFICIENT_INFORMATION")
