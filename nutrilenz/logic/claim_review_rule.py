from ..domain.flag import Flag
from .evaluation_context import EvaluationContext
from .rule import Rule


class ClaimReviewRule(Rule):
    """Multi-condition rule kept from Part 1: a claim was given AND the AI judged it
    QUESTIONABLE AND the AI is at least MEDIUM confident. LOW confidence goes to
    manual review instead."""

    @property
    def flag(self) -> Flag:
        return Flag.CLAIM_REVIEW

    def applies(self, context: EvaluationContext, flags_so_far: list[Flag]) -> bool:
        return (context.product.has_claim
                and context.ai.claim_status == "QUESTIONABLE"
                and context.ai.confidence in ("MEDIUM", "HIGH"))
