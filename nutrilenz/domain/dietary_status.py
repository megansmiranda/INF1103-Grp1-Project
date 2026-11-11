from enum import Enum


class DietaryStatus(Enum):
    POSSIBLE_CONCERN = "POSSIBLE_CONCERN"
    NO_MATCH = "NO_MATCH"
    NOT_CHECKED = "NOT_CHECKED"

    @property
    def label(self) -> str:
        return {self.POSSIBLE_CONCERN: "Possible concern", self.NO_MATCH: "No match found",
                self.NOT_CHECKED: "Not checked – no ingredient list"}[self]
