from flask import Flask, redirect, render_template, request, url_for

from ..domain.recommendation_focus import RecommendationFocus
from ..errors.validation_error import ValidationError
from .page_controller import PageController


class RecommendationPages(PageController):
    """Pick a focus and category from fixed options; the result runs as a background job."""

    def register(self, app: Flask) -> None:
        app.add_url_rule("/recommendations", "recommendations", self.recommendations,
                         methods=["GET", "POST"])

    def _form_page(self, categories: list[str], errors: dict, focuses: list[str],
                   chosen_categories: list[str]):
        return render_template("recommendations.html", focuses=list(RecommendationFocus),
                               categories=categories, errors=errors,
                               selected_focuses=focuses, selected_categories=chosen_categories)

    def recommendations(self):
        categories = self._ctx.recommendations.categories()
        if request.method == "GET":
            return self._form_page(categories, {}, [RecommendationFocus.BEST_MATCH.name], [])
        try:
            options = self._ctx.forms.recommendation_options(request.form, categories)
        except ValidationError as error:
            return self._form_page(categories, error.field_errors, request.form.getlist("focus"),
                                   request.form.getlist("category")), 400
        user = self._user
        job = self._ctx.jobs.submit(user.user_id, "recommendation",
                                    lambda job: self._ctx.recommendations.recommend(user, options, job))
        return redirect(url_for("job", job_id=job.job_id))
