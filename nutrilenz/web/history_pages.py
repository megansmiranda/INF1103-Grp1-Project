from flask import Flask, abort, flash, redirect, render_template, request, url_for

from ..domain.flag import Flag
from ..errors.data_error import DataError
from ..errors.error_messages import ErrorMessages
from .page_controller import PageController


class HistoryPages(PageController):
    """Dashboard summary, history with filters, one saved analysis, delete."""

    def register(self, app: Flask) -> None:
        app.add_url_rule("/", "dashboard", self.dashboard)
        app.add_url_rule("/history", "history", self.history)
        app.add_url_rule("/history/<int:analysis_id>", "analysis_detail", self.detail)
        app.add_url_rule("/history/<int:analysis_id>/delete", "delete_analysis", self.delete,
                         methods=["POST"])

    def dashboard(self):
        records = self._ctx.data.history(self._user.user_id)
        counts = {flag.value: sum(1 for r in records if r.has_flag(flag)) for flag in Flag
                  if flag is not Flag.DIETARY_REVIEW}  # dietary dashboard summary is out of scope
        average = round(sum(r.score for r in records) / len(records), 1) if records else None
        return render_template("dashboard.html", recent=records[:5], total=len(records),
                               counts=counts, average=average)

    def history(self):
        flag_name = request.args.get("flag", "")
        search = request.args.get("q", "").strip()[:120]
        flag = Flag[flag_name] if flag_name in Flag.__members__ else None
        records = self._ctx.data.history(self._user.user_id, flag, search or None)
        return render_template("history.html", records=records, flag=flag_name, q=search,
                               flags=list(Flag))

    def detail(self, analysis_id: int):
        try:
            record = self._ctx.data.get_analysis(self._user.user_id, analysis_id)
        except DataError:
            abort(404)
        return render_template("analysis_detail.html", record=record)

    def delete(self, analysis_id: int):
        try:
            self._ctx.data.delete_analysis(self._user.user_id, analysis_id)
            flash("Analysis deleted. Your other analyses were kept.")
        except DataError as error:
            flash("Nothing was deleted. " + ErrorMessages.text(error.code))
        return redirect(url_for("history"))
