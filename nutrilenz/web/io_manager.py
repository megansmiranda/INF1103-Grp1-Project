import logging
from pathlib import Path

from flask import Flask, flash, g, redirect, render_template, request, url_for

from ..domain.flag import Flag
from ..domain.dietary_check_factory import DietaryCheckFactory
from ..domain.nutrients import Nutrient
from ..errors.data_error import DataError
from ..errors.error_messages import ErrorMessages
from ..errors.nutrilenz_error import NutriLenzError
from .account_pages import AccountPages
from .analysis_pages import AnalysisPages
from .history_pages import HistoryPages
from .page_controller import PageController
from .recommendation_pages import RecommendationPages
from .web_context import WebContext
from .csrf_guard import CsrfGuard
from .dietary_presenter import DietaryPresenter

logger = logging.getLogger("nutrilenz.web")


class WebIOManager:
    """IO Manager for the web version. Collects and validates input through forms
    and shows results as pages. It never applies business rules itself."""

    STATIC_ENDPOINTS = ("static",)
    MAX_UPLOAD_BYTES = 45 * 1024 * 1024          # 5 photos of up to 8 MB plus form fields

    def __init__(self, context: WebContext, secret_key: str):
        self._ctx = context
        self._csrf = CsrfGuard()
        root = Path(__file__).resolve().parent
        self._app = Flask("nutrilenz", template_folder=str(root / "templates"),
                          static_folder=str(root / "static"))
        self._app.config.update(SECRET_KEY=secret_key, MAX_CONTENT_LENGTH=self.MAX_UPLOAD_BYTES,
                                SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")
        # The page groups are created here and belong to this manager
        self._controllers: list[PageController] = [
            AccountPages(context), AnalysisPages(context),
            HistoryPages(context), RecommendationPages(context)]
        self._public = set(self.STATIC_ENDPOINTS)
        for controller in self._controllers:
            controller.register(self._app)
            self._public.update(controller.PUBLIC_ENDPOINTS)
        self._app.before_request(self._before_request)
        self._app.context_processor(self._template_values)
        self._app.register_error_handler(NutriLenzError, self._app_error)
        self._app.register_error_handler(404, self._not_found)
        self._app.register_error_handler(413, self._too_large)

    @property
    def app(self) -> Flask:
        return self._app

    def run(self, host: str, port: int, details: str) -> None:
        shown_host = "localhost" if host in ("0.0.0.0", "127.0.0.1") else host
        print(f"NutriLenz is running on http://{shown_host}:{port}  ({details})", flush=True)
        # threaded=True: each browser request gets its own thread; AI work runs in the job pool
        self._app.run(host=host, port=port, threaded=True, debug=False, use_reloader=False)

    def _before_request(self):
        if request.endpoint in self.STATIC_ENDPOINTS:
            return None
        self._ctx.data.ensure_ready()               # DB_UNAVAILABLE -> error page
        if request.method == "POST" and not self._csrf.is_valid(request.form.get(CsrfGuard.FIELD)):
            flash("The form expired. Please try again.")
            return redirect(request.path if request.endpoint in self._public else url_for("dashboard"))
        g.user = None
        user_id = self._ctx.login.user_id
        if user_id is not None:
            try:
                g.user = self._ctx.data.get_user(user_id)
            except DataError as error:
                if error.code != "USER_NOT_FOUND":
                    raise
                self._ctx.login.log_out()
        if g.user is None and request.endpoint not in self._public:
            return redirect(url_for("login"))
        return None

    def _template_values(self) -> dict:
        return {"csrf_token": self._csrf.token, "error_text": ErrorMessages.text,
                "current_user": g.get("user"), "nutrients": list(Nutrient), "Flag": Flag,
                "dietary_options": DietaryCheckFactory.options(), "dietary_view": DietaryPresenter}

    def _app_error(self, error: NutriLenzError):
        logger.warning("Request failed with %s: %s", error.code, error.detail)
        status = 503 if error.code == "DB_UNAVAILABLE" else 400
        return render_template("error.html", message=ErrorMessages.text(error.code)), status

    @staticmethod
    def _not_found(error):
        return render_template("error.html", message="That page or record could not be found."), 404

    @staticmethod
    def _too_large(error):
        return render_template("error.html", message="The upload is too large (max 8 MB per photo)."), 413
