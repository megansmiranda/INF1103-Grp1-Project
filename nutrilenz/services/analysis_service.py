import logging

from ..ai.ai_manager import AIManager
from ..ai.label_image import LabelImage
from ..ai.label_reading import LabelReading
from ..data.data_manager import DataManager
from ..domain.analysis import Analysis
from ..domain.product import Product
from ..domain.user import User
from ..errors.ai_error import AIError
from ..errors.data_error import DataError
from ..logic.logic_manager import LogicManager
from .job import Job
from .analysis_outcome import AnalysisOutcome

logger = logging.getLogger("nutrilenz.services")


class AnalysisService:
    """The pipeline for one product: AI -> Logic -> Data.
    It works with the managers it is given; it does not create or own them."""

    def __init__(self, ai: AIManager, logic: LogicManager, data: DataManager):
        self._ai = ai
        self._logic = logic
        self._data = data

    def read_label(self, image: LabelImage, job: Job | None = None) -> LabelReading:
        if job:
            job.set_step("Reading the label photo")
        reading = self._ai.read_label_image(image)
        if not reading.readable:
            raise AIError("UNREADABLE_IMAGE")
        return reading

    def unusual_number_warnings(self, product: Product) -> list[str]:
        return self._logic.check_unusual_numbers(product)

    def analyse(self, user: User, product: Product, job: Job | None = None) -> AnalysisOutcome:
        """Every record goes through the AI. If saving fails the result is still returned."""
        report = self._logic.check_dietary(product, user.profile)
        if job:
            job.set_step("Asking the AI to interpret the label")
        ai_result = self._ai.analyse_label(product, user.profile, report)

        if job:
            job.set_step("Applying the rules")
        evaluation = self._logic.evaluate(product, user.profile, ai_result.value, report)
        analysis = Analysis(user_id=user.user_id, product=product,
                            profile_snapshot=user.profile.snapshot(),
                            ai_analysis=ai_result.value, flags=list(evaluation.flags),
                            goal_results=list(evaluation.goal_results), score=evaluation.score,
                            provider=ai_result.provider, dietary_report=evaluation.dietary_report)

        if job:
            job.set_step("Saving the result")
        try:
            self._data.save_analysis(analysis)
        except DataError as error:
            logger.error("Analysis finished but was not saved: %s", error.code)
            return AnalysisOutcome(analysis, saved=False, error_code=error.code)
        return AnalysisOutcome(analysis, saved=True)
