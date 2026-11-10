import json
from abc import ABC, abstractmethod

from ..domain.profile import Profile
from .ai_request import AIRequest
from .schema_checker import SchemaChecker
from .prompt_text import DATA_MARKER, DATA_REMINDER


class AITask(ABC):
    """Interface for one kind of AI job. Each task owns its prompt and the
    schema its reply must follow, so a new AI feature is a new task class and
    the AI Manager does not change."""

    def __init__(self):
        self._checker = SchemaChecker()

    @property
    @abstractmethod
    def name(self) -> str:
        """Short name used in logs."""

    @property
    def needs_image(self) -> bool:
        return False

    @abstractmethod
    def build_request(self) -> AIRequest:
        """Rules + data to send."""

    @abstractmethod
    def parse(self, data: dict):
        """Check the decoded JSON reply and return a result object. Raises ValueError."""

    @staticmethod
    def _as_data(payload: dict) -> str:
        return DATA_MARKER.strip() + "\n" + json.dumps(
            payload, ensure_ascii=False, allow_nan=False, indent=2) + DATA_REMINDER

    @staticmethod
    def _goal_phrase(profile: Profile) -> list[str]:
        """Goals in words. Target numbers are NOT sent: Logic compares numbers, AI explains."""
        phrases = []
        for goal in profile.goals:
            word = "keep low" if goal.direction == "MAX" else "get more"
            phrases.append(word + ": " + goal.nutrient.label.lower())
        return phrases
