import logging
import time
from typing import Callable

from ..app_config import AppConfig
from ..domain.product import Product
from ..domain.dietary_report import DietaryReport
from ..domain.recommendation_options import RecommendationOptions
from ..domain.scored_product import ScoredProduct
from ..domain.profile import Profile
from ..errors.ai_error import AIError
from .ai_provider import AIProvider
from .gemini_provider import GeminiProvider
from .groq_provider import GroqProvider
from .http_client import HttpClient
from .ai_result import AIResult
from .label_image import LabelImage
from .label_reading import LabelReading
from .recommendation_advice import RecommendationAdvice
from .ai_task import AITask
from .label_analysis_task import LabelAnalysisTask
from .label_extraction_task import LabelExtractionTask
from .recommendation_task import RecommendationTask
from .json_reply_parser import JsonReplyParser

logger = logging.getLogger("nutrilenz.ai")


class AIManager:
    """Runs any AITask: tries each provider in order (Gemini first, Groq as backup),
    retries once per provider, and only returns replies that passed the task's schema."""

    MAX_ATTEMPTS_PER_PROVIDER = 2
    NON_RETRYABLE = ("CONFIGURATION_ERROR", "AUTHENTICATION_ERROR", "NO_IMAGE_PROVIDER")

    def __init__(self, providers: list[AIProvider], sleep: Callable[[float], None] = time.sleep):
        self._providers = list(providers)
        self._parser = JsonReplyParser()
        self._sleep = sleep

    @classmethod
    def from_config(cls, config: AppConfig) -> "AIManager":
        """Creates the providers that have a key. The manager owns them."""
        http = HttpClient(config.ai_timeout_seconds)
        providers: list[AIProvider] = []
        if config.gemini_api_key:
            providers.append(GeminiProvider(config.gemini_api_key, config.gemini_model, http))
        if config.groq_api_key:
            providers.append(GroqProvider(config.groq_api_key, config.groq_model, http,
                                          config.groq_vision_model))
        return cls(providers)

    @property
    def provider_names(self) -> list[str]:
        return [provider.name for provider in self._providers]

    def run(self, task: AITask) -> AIResult:
        providers = [p for p in self._providers if p.supports_images or not task.needs_image]
        if not self._providers:
            logger.error("No API key found. Set GEMINI_API_KEY and/or GROQ_API_KEY in .env")
            raise AIError("CONFIGURATION_ERROR")
        if not providers:
            raise AIError("NO_IMAGE_PROVIDER")

        base_request = task.build_request()
        last_error = "API_UNAVAILABLE"
        for provider in providers:
            request = base_request
            for attempt in range(1, self.MAX_ATTEMPTS_PER_PROVIDER + 1):
                try:
                    raw_text = provider.generate(request)
                except AIError as error:
                    last_error = error.code
                    logger.warning("%s %s attempt %d failed: %s", task.name, provider.name,
                                   attempt, error.code)
                    if error.code in self.NON_RETRYABLE:
                        break                       # wrong key/model: go to the backup
                    if error.code == "API_UNAVAILABLE" and attempt < self.MAX_ATTEMPTS_PER_PROVIDER:
                        self._sleep(1)              # short pause before asking a busy server again
                    continue
                try:
                    value = task.parse(self._parser.parse(raw_text))
                    return AIResult(value, provider.name)
                except ValueError as problem:
                    # Bad output: retry once and tell the model what was wrong
                    last_error = "INVALID_RESPONSE"
                    logger.warning("%s %s attempt %d invalid output: %s", task.name,
                                   provider.name, attempt, problem)
                    request = base_request.with_feedback(str(problem))
        logger.error("All AI providers failed for %s. Last error: %s", task.name, last_error)
        raise AIError(last_error)

    # Shortcuts used by the services
    def analyse_label(self, product: Product, profile: Profile,
                      dietary_report: DietaryReport | None = None) -> AIResult:
        """value is an AIAnalysis."""
        return self.run(LabelAnalysisTask(product, profile, dietary_report))

    def read_label_image(self, image: LabelImage) -> LabelReading:
        return self.run(LabelExtractionTask(image)).value

    def advise(self, profile: Profile, options: RecommendationOptions,
               candidates: list[ScoredProduct]) -> RecommendationAdvice:
        return self.run(RecommendationTask(profile, options, candidates)).value
