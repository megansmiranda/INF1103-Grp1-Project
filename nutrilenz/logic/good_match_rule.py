from ..domain.flag import Flag
from .evaluation_context import EvaluationContext
from .rule import Rule


class GoodMatchRule(Rule):
    """Every goal met, no other flag, and the AI agrees. It is about the chosen goals
    only, not a promise that the food is healthy overall."""

    @property
    def flag(self) -> Flag:
        return Flag.GOOD_MATCH

    def applies(self, context: EvaluationContext, flags_so_far: list[Flag]) -> bool:
        return (context.all_goals_met()
                and not flags_so_far
                and context.ai.goal_alignment == "ALIGNED"
                and context.ai.claim_status in ("CONSISTENT", "NO_CLAIM"))
