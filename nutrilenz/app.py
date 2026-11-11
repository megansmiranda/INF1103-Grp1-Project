import logging

from .ai.ai_manager import AIManager
from .app_config import AppConfig
from .data.data_manager import DataManager
from .data.memory_store import InMemoryDataStore
from .data.mysql_store import MySQLDataStore
from .data.data_store import DataStore
from .data.seeder import DemoDataSeeder
from .errors.data_error import DataError
from .logic.logic_manager import LogicManager
from .services.analysis_service import AnalysisService
from .services.job_manager import JobManager
from .services.recommendation_service import RecommendationService
from .web.web_context import WebContext
from .web.io_manager import WebIOManager

logger = logging.getLogger("nutrilenz")


class NutriLenzApp:
    """Builds the four managers and the services, wires them together and runs the website."""

    def __init__(self, config: AppConfig, store: DataStore | None = None, ai: AIManager | None = None):
        self._config = config
        self._data = DataManager(store or self._make_store(config))
        self._ai = ai or AIManager.from_config(config)
        self._logic = LogicManager()
        self._jobs = JobManager(config.worker_threads)
        context = WebContext(self._data,
                             AnalysisService(self._ai, self._logic, self._data),
                             RecommendationService(self._ai, self._logic, self._data),
                             self._jobs)
        self._io = WebIOManager(context, config.secret_key)

    @classmethod
    def from_environment(cls) -> "NutriLenzApp":
        config = AppConfig.from_environment()
        cls._setup_logging(config)
        return cls(config)

    @staticmethod
    def _make_store(config: AppConfig) -> DataStore:
        if config.storage == "memory":
            return InMemoryDataStore()
        return MySQLDataStore(config.db_host, config.db_port, config.db_user,
                              config.db_password, config.db_name)

    @staticmethod
    def _setup_logging(config: AppConfig) -> None:
        """Errors go to a log file, never to the user's screen."""
        try:
            logging.basicConfig(filename=str(config.log_path), level=logging.INFO,
                                format="%(asctime)s %(levelname)s %(name)s: %(message)s")
        except OSError:
            logging.basicConfig(level=logging.WARNING)

    @property
    def web_app(self):
        """The Flask app (used by tests)."""
        return self._io.app

    def prepare_data(self) -> None:
        """Create tables and add demo data on first run. A database that is still
        starting up is not fatal: pages retry and show a friendly message meanwhile."""
        try:
            self._data.ensure_ready()
            if self._config.seed_demo_data:
                DemoDataSeeder(self._data, self._logic).seed_if_empty()
        except DataError as error:
            logger.error("Database not ready at start-up: %s", error.code)

    def run(self) -> None:
        self.prepare_data()
        details = (f"AI: {', '.join(self._ai.provider_names) or 'none set up'}; "
                   f"storage: {self._config.storage}")
        try:
            self._io.run(self._config.host, self._config.port, details)
        finally:
            self._jobs.shutdown()
