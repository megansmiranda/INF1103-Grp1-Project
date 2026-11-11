from abc import ABC, abstractmethod

from ..domain.flag import Flag
from .evaluation_context import EvaluationContext


class Rule(ABC):
    """One business rule that may add one flag. Rules run in a fixed order and
    can see the flags already given, so a new rule is just a new subclass."""

    @property
    @abstractmethod
    def flag(self) -> Flag:
        """The flag this rule adds."""

    @abstractmethod
    def applies(self, context: EvaluationContext, flags_so_far: list[Flag]) -> bool:
        """True if the flag should be added."""
