from ..domain.flag import Flag
from .evaluation_context import EvaluationContext
from .rule import Rule


class DietaryReviewRule(Rule):
    """Only a matched ingredient adds this flag; no match is not an assurance."""

    @property
    def flag(self) -> Flag:
        return Flag.DIETARY_REVIEW

    def applies(self, context: EvaluationContext, flags_so_far: list[Flag]) -> bool:
        return context.dietary_report.has_concern
