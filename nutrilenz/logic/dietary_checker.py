import re
from functools import lru_cache

from ..domain.dietary_check import DietaryCheck
from ..domain.dietary_keywords import DietaryKeywords
from ..domain.dietary_report import DietaryReport
from ..domain.dietary_result import DietaryResult
from ..domain.dietary_status import DietaryStatus


class DietaryChecker:
    """Whole-word matching, independent of AI and Product's custom avoid-list matcher."""

    @staticmethod
    @lru_cache(maxsize=256)
    def _pattern(words: tuple[str, ...]) -> re.Pattern:
        terms = []
        for word in sorted(words, key=len, reverse=True):
            suffix = "es" if word.endswith(("s", "x", "ch", "sh")) else "s"
            terms.append(re.escape(word).replace(r"\ ", r"\s+") + "(?:" + suffix + ")?")
        return re.compile(r"(?<!\w)(?:" + "|".join(terms) + r")(?!\w)", re.IGNORECASE)

    def check(self, text: str | None, check: DietaryCheck) -> DietaryResult:
        if not text or not text.strip():
            return DietaryResult(check.key, check.label, DietaryStatus.NOT_CHECKED)
        candidates = set()
        for group in check.keyword_groups:
            exceptions = DietaryKeywords.EXCEPTIONS.get(group, ())
            excluded = [m.span() for m in self._pattern(exceptions).finditer(text)] if exceptions else []
            for match in self._pattern(DietaryKeywords.GROUPS[group]).finditer(text):
                start, end = match.span()
                if not any(a <= start < b for a, b in excluded):
                    candidates.add((start, end))
        # Prefer the longer phrase when a group also matched a word inside it.
        spans = []
        for start, end in sorted(candidates, key=lambda s: (s[0], -s[1])):
            if not spans or start >= spans[-1][1]:
                spans.append((start, end))
        words = {}
        for a, b in spans:
            words.setdefault(text[a:b].casefold(), text[a:b])
        status = DietaryStatus.POSSIBLE_CONCERN if spans else DietaryStatus.NO_MATCH
        return DietaryResult(check.key, check.label, status, tuple(words.values()), tuple(spans))

    def evaluate(self, ingredient_text: str | None, checks: tuple[DietaryCheck, ...]) -> DietaryReport:
        return DietaryReport(tuple(self.check(ingredient_text, check) for check in checks), ingredient_text or "",
                             rules_version="image-rules-v1")

