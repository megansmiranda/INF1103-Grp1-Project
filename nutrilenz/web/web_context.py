from ..data.data_manager import DataManager
from ..services.analysis_service import AnalysisService
from ..services.job_manager import JobManager
from ..services.recommendation_service import RecommendationService
from .forms import FormParser
from .login_session import LoginSession


class WebContext:
    """The shared things every page controller needs, passed in one object."""

    def __init__(self, data: DataManager, analysis: AnalysisService,
                 recommendations: RecommendationService, jobs: JobManager):
        self.data = data
        self.analysis = analysis
        self.recommendations = recommendations
        self.jobs = jobs
        self.forms = FormParser()
        self.login = LoginSession()
