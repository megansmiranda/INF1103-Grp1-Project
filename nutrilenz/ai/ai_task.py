import json
import re
from abc import ABC, abstractmethod

from ..domain.dietary_keywords import DietaryKeywords
from ..domain.dietary_report import DietaryReport
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

    @staticmethod
    def _dietary_preferences(profile: Profile) -> list[dict]:
        return [{"key": check.key, "name": check.label,
                 "words_to_avoid": list(dict.fromkeys(word for group in check.keyword_groups
                                                       for word in DietaryKeywords.GROUPS[group])),
                 "word_exceptions": list(dict.fromkeys(word for group in check.keyword_groups
                                                        for word in DietaryKeywords.EXCEPTIONS.get(group, ())))}
                for check in profile.dietary_checks]

    @staticmethod
    def _dietary_facts(report: DietaryReport) -> list[dict]:
        return [{"key": result.key, "name": result.label, "status": result.status.value,
                 "matched_words": list(result.matched_words)} for result in report.results]

    @staticmethod
    def _check_dietary_wording(texts: list[str]) -> None:
        if any(re.search(r"\b(?:safe|suitable|certified)\b|\bfree[\s-]+from\b", text, re.I)
               for text in texts):
            raise ValueError("Do not describe products as safe, suitable, certified or free from anything")
