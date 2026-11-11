from flask import Flask, jsonify, redirect, render_template, request, url_for

from ..errors.error_messages import ErrorMessages
from ..errors.validation_error import ValidationError
from ..services.job import Job
from ..services.job_status import JobStatus
from .page_controller import PageController


class AnalysisPages(PageController):
    """Type in a label or upload photos, check the values, and run the analysis in the background."""

    def register(self, app: Flask) -> None:
        app.add_url_rule("/analyse", "analyse", self.analyse, methods=["GET", "POST"])
        app.add_url_rule("/upload", "upload", self.upload, methods=["POST"])
        app.add_url_rule("/batches/<batch_id>", "batch", self.batch)
        app.add_url_rule("/batches/<batch_id>/analyse", "analyse_batch", self.analyse_batch,
                         methods=["POST"])
        app.add_url_rule("/jobs/<job_id>", "job", self.job)
        app.add_url_rule("/api/jobs/<job_id>", "job_status", self.job_status)
        app.add_url_rule("/api/batches/<batch_id>", "batch_status", self.batch_status)

    def analyse(self):
        if request.method == "GET":
            return render_template("analyse.html", errors={}, values={}, warnings=[])
        try:
            product = self._ctx.forms.product(request.form)
        except ValidationError as error:
            return render_template("analyse.html", errors=error.field_errors,
                                   values=request.form, warnings=[]), 400

        # Ask before spending an AI call on odd numbers or a repeat
        notes = self._ctx.analysis.unusual_number_warnings(product)
        previous = self._ctx.data.previous_analyses(self._user.user_id, product.name)
        if previous:
            notes.append(f"You have analysed '{product.name}' {previous} time(s) before. "
                         "Analysing again creates a new record.")
        if notes and request.form.get("confirmed") != "yes":
            return render_template("analyse.html", errors={}, values=request.form, warnings=notes)

        user = self._user
        job = self._ctx.jobs.submit(user.user_id, "analysis",
                                    lambda job: self._ctx.analysis.analyse(user, product, job))
        return redirect(url_for("job", job_id=job.job_id))

    def upload(self):
        try:
            images = self._ctx.forms.photos(request.files.getlist("photos"))
        except ValidationError as error:
            return render_template("analyse.html", errors=error.field_errors,
                                   values={}, warnings=[]), 400
        works = [self._reader(image) for image in images]
        batch = self._ctx.jobs.submit_batch(self._user.user_id, "extraction", works)
        return redirect(url_for("batch", batch_id=batch.batch_id))

    def _reader(self, image):
        return lambda job: self._ctx.analysis.read_label(image, job)

    def _analyser(self, user, product):
        return lambda job: self._ctx.analysis.analyse(user, product, job)

    @staticmethod
    def _prefill(index: int, job: Job) -> dict:
        fields = job.result.product_fields
        prefix = f"p{index}_"
        values = {prefix + key: fields[key] or "" for key in fields if key != "nutrition"}
        for key, value in fields["nutrition"].items():
            values[prefix + "n_" + key] = "" if value is None else f"{value:g}"
        values["include_" + str(index)] = "on"
        return values

    def batch(self, batch_id: str):
        batch = self._batch_or_404(batch_id)
        values = {}
        if batch.finished and batch.jobs[0].kind == "extraction":
            for index, job in enumerate(batch.jobs):
                if job.status is JobStatus.DONE:
                    values.update(self._prefill(index, job))
        return render_template("batch.html", batch=batch, values=values, errors={})

    def analyse_batch(self, batch_id: str):
        batch = self._batch_or_404(batch_id)
        products, errors = [], {}
        for index, job in enumerate(batch.jobs):
            if job.status is not JobStatus.DONE or request.form.get(f"include_{index}") != "on":
                continue
            try:
                products.append(self._ctx.forms.product(request.form, prefix=f"p{index}_"))
            except ValidationError as error:
                errors.update(error.field_errors)
        if not products and not errors:
            errors["form"] = "Tick at least one product to analyse."
        if errors:
            return render_template("batch.html", batch=batch, values=request.form, errors=errors), 400
        user = self._user
        new_batch = self._ctx.jobs.submit_batch(user.user_id, "analysis",
                                                [self._analyser(user, p) for p in products])
        return redirect(url_for("batch", batch_id=new_batch.batch_id))

    def job(self, job_id: str):
        return render_template("job.html", job=self._job_or_404(job_id))

    @staticmethod
    def _job_json(job: Job) -> dict:
        return {"id": job.job_id, "status": job.status.value, "step": job.step,
                "finished": job.finished,
                "error": ErrorMessages.text(job.error_code) if job.error_code else None}

    def job_status(self, job_id: str):
        return jsonify(self._job_json(self._job_or_404(job_id)))

    def batch_status(self, batch_id: str):
        batch = self._batch_or_404(batch_id)
        return jsonify({"finished": batch.finished,
                        "jobs": [self._job_json(job) for job in batch.jobs]})
