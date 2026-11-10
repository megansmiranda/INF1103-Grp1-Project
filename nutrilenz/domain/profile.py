from .goal import Goal
from .goal_factory import GoalFactory


class Profile:
    """A user's goals and ingredients to avoid.
    The profile creates its own Goal objects from plain specs, so goals only
    exist as part of a profile and are replaced or removed with it (composition)."""

    MAX_GOALS = 5

    def __init__(self, goal_specs: list[dict], avoid_ingredients: list[str] | None = None):
        self._goals: list[Goal] = []
        self._avoid: list[str] = []
        self.replace_goals(goal_specs)
        self.replace_avoid_list(avoid_ingredients or [])

    @property
    def goals(self) -> tuple[Goal, ...]:
        return tuple(self._goals)

    @property
    def avoid_ingredients(self) -> tuple[str, ...]:
        return tuple(self._avoid)

    def replace_goals(self, goal_specs: list[dict]) -> None:
        goals = [GoalFactory.from_dict(spec) for spec in goal_specs]
        if not goals:
            raise ValueError("Choose at least one goal")
        if len(goals) > self.MAX_GOALS:
            raise ValueError(f"Choose at most {self.MAX_GOALS} goals")
        nutrients = [goal.nutrient for goal in goals]
        if len(set(nutrients)) != len(nutrients):
            raise ValueError("Each nutrient can only be used in one goal")
        self._goals = goals

    def replace_avoid_list(self, words: list[str]) -> None:
        cleaned = []
        for word in words:
            word = word.strip()
            if word and word.casefold() not in [w.casefold() for w in cleaned]:
                cleaned.append(word)
        self._avoid = cleaned

    def describe_goals(self) -> list[str]:
        return [goal.describe() for goal in self._goals]

    def snapshot(self) -> dict:
        """Plain copy saved with each analysis, so old results keep their old targets."""
        return {"goals": [goal.to_dict() for goal in self._goals],
                "avoid_ingredients": list(self._avoid)}

    @classmethod
    def from_snapshot(cls, data: dict) -> "Profile":
        return cls(data["goals"], data.get("avoid_ingredients", []))
