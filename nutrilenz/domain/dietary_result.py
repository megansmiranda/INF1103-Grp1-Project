from dataclasses import dataclass

from .dietary_status import DietaryStatus


@dataclass(frozen=True)
class DietaryResult:
    key: str
    label: str
    status: DietaryStatus
    matched_words: tuple[str, ...] = ()
    matched_spans: tuple[tuple[int, int], ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "matched_words", tuple(self.matched_words))
        object.__setattr__(self, "matched_spans", tuple(tuple(span) for span in self.matched_spans))

    def to_dict(self) -> dict:
        return {"key": self.key, "label": self.label, "status": self.status.value,
                "matched_words": list(self.matched_words),
                "matched_spans": [list(span) for span in self.matched_spans]}

    @classmethod
    def from_dict(cls, data: dict) -> "DietaryResult":
        return cls(data["key"], data["label"], DietaryStatus(data["status"]),
                   data.get("matched_words", ()), data.get("matched_spans", ()))
