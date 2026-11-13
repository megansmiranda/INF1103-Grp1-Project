"""Shared test helpers. No test needs a live AI API or a running database."""
import json
import sys
import urllib.request
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nutrilenz.ai.ai_manager import AIManager                     # noqa: E402
from nutrilenz.ai.gemini_provider import GeminiProvider            # noqa: E402
from nutrilenz.ai.groq_provider import GroqProvider                # noqa: E402
from nutrilenz.data.data_manager import DataManager                # noqa: E402
from nutrilenz.data.memory_store import InMemoryDataStore          # noqa: E402
from nutrilenz.domain.ai_analysis import AIAnalysis                # noqa: E402
from nutrilenz.domain.product import Product                       # noqa: E402
from nutrilenz.domain.profile import Profile                       # noqa: E402
from nutrilenz.errors.ai_error import AIError                      # noqa: E402
from nutrilenz.logic.logic_manager import LogicManager             # noqa: E402


@pytest.fixture(autouse=True)
def offline_ai(monkeypatch):
    """Keep every test offline even when Compose supplies a developer's .env."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    def reject_live_http(*args, **kwargs):
        raise AssertionError("Live AI HTTP is forbidden in tests; inject FakeHttp instead")

    monkeypatch.setattr(urllib.request, "urlopen", reject_live_http)


class FakeHttp:
    """Stands in for HttpClient. Returns scripted replies (or raises scripted AIErrors)
    and remembers every request body, so real provider classes can be tested offline."""

    def __init__(self, replies: list):
        self._replies = list(replies)
        self.bodies: list[dict] = []
        self.urls: list[str] = []
        self.headers: list[dict] = []

    def post_json(self, url: str, headers: dict, body: dict) -> dict:
        self.urls.append(url)
        self.headers.append(headers)
        self.bodies.append(body)
        if not self._replies:
            raise AIError("API_UNAVAILABLE")
        reply = self._replies.pop(0)
        if isinstance(reply, AIError):
            raise reply
        return reply

    @property
    def calls(self) -> int:
        return len(self.bodies)


class Replies:
    """Builds provider-shaped replies around a JSON answer."""

    @staticmethod
    def gemini(answer) -> dict:
        text = answer if isinstance(answer, str) else json.dumps(answer)
        return {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": text}]}}]}

    @staticmethod
    def groq(answer) -> dict:
        text = answer if isinstance(answer, str) else json.dumps(answer)
        return {"choices": [{"finish_reason": "stop", "message": {"content": text}}]}


def analysis_answer(**changes) -> dict:
    """A valid label-analysis answer; change any field with keyword arguments."""
    answer = {
        "relevant_ingredients": ["brown rice syrup"],
        "goal_alignment": "POOR_ALIGNMENT",
        "claim_status": "QUESTIONABLE",
        "evidence": ["sugar_g: 14"],
        "explanation": "Brown rice syrup is a sugar. 14 g per serving is high for a low-sugar goal.",
        "confidence": "HIGH",
        "suggestions": ["Choose plain oats."],
        "suggested_products": [{"name": "FairPrice Australian Rolled Oats", "brand": "FairPrice",
                                "reason": "No added sugar."}],
    }
    answer.update(changes)
    return answer


def make_ai(*replies, groq_replies=None, sleep=None) -> tuple[AIManager, FakeHttp, FakeHttp]:
    """An AIManager with a real GeminiProvider (and GroqProvider) on fake HTTP."""
    gemini_http = FakeHttp(list(replies))
    groq_http = FakeHttp(list(groq_replies or []))
    providers = [GeminiProvider("test-key", "gemini-test", gemini_http),
                 GroqProvider("test-key", "groq-test", groq_http, "groq-vision-test")]
    return AIManager(providers, sleep=sleep or (lambda seconds: None)), gemini_http, groq_http


def product(**changes) -> Product:
    data = {"product_name": "Example Cereal", "brand": None, "category": "Cereal",
            "nutrition": {"sugar_g": 14.0, "protein_g": 6.0, "sodium_mg": 180.0, "calories_kcal": 210.0},
            "ingredient_text": "Oats, brown rice syrup, cocoa, maltodextrin",
            "marketing_claim": "Naturally sweetened"}
    data.update(changes)
    return Product.from_dict(data)


def profile(*goals, avoid=None) -> Profile:
    specs = list(goals) or [{"nutrient": "sugar_g", "direction": "MAX", "target": 10}]
    return Profile(specs, avoid or [])


def ai_analysis(**changes) -> AIAnalysis:
    return AIAnalysis.from_dict(analysis_answer(**changes))


SUGAR_MAX_10 = {"nutrient": "sugar_g", "direction": "MAX", "target": 10}
CALORIES_MAX_200 = {"nutrient": "calories_kcal", "direction": "MAX", "target": 200}
PROTEIN_MIN_15 = {"nutrient": "protein_g", "direction": "MIN", "target": 15}


@pytest.fixture
def logic() -> LogicManager:
    return LogicManager()


@pytest.fixture
def data() -> DataManager:
    manager = DataManager(InMemoryDataStore())
    manager.ensure_ready()
    return manager
