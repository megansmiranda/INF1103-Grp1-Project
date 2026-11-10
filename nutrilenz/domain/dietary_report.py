from dataclasses import dataclass

from .dietary_status import DietaryStatus
from .dietary_result import DietaryResult


@dataclass(frozen=True)
class DietaryReport:
    """Snapshot of the exact text and outcomes checked, never recomputed on load."""

    results: tuple[DietaryResult, ...] = ()
    ingredient_text: str = ""
    rules_version: str = "not-run"
    score_penalty: float = 0.0  # historical metadata only; never applied to new scores

    def __post_init__(self):
        object.__setattr__(self, "results", tuple(self.results))

    @property
    def concern_count(self) -> int:
        return sum(result.status is DietaryStatus.POSSIBLE_CONCERN for result in self.results)

    @property
    def has_concern(self) -> bool:
        return self.concern_count > 0

    def to_dict(self) -> dict:
        return {"results": [r.to_dict() for r in self.results], "ingredient_text": self.ingredient_text,
                "rules_version": self.rules_version, "score_penalty": self.score_penalty}

    @classmethod
    def from_dict(cls, data: dict | list | None, ingredient_text: str = "") -> "DietaryReport":
        if not data:
            return cls()
        # Read snapshots saved by the earlier feature without applying today's lists.
        if isinstance(data, list):
            return cls(tuple(DietaryResult.from_dict(r) for r in data), ingredient_text, "legacy")
        return cls(tuple(DietaryResult.from_dict(r) for r in data["results"]),
                   data["ingredient_text"], data.get("rules_version", "legacy"),
                   float(data.get("score_penalty", 0)))
