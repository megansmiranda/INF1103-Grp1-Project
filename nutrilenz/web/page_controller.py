from abc import ABC, abstractmethod
from flask import Flask, abort, g

from ..domain.product import Product
from ..domain.user import User
from ..errors.validation_error import ValidationError
from ..services.batch import Batch
from ..services.job import Job
from ..services.job_status import JobStatus
from .web_context import WebContext


class PageController(ABC):
    """Base class for a group of related pages. Each subclass registers its own
    routes, so adding a page group does not change the others."""

    PUBLIC_ENDPOINTS: tuple[str, ...] = ()       # pages that work without logging in

    def __init__(self, context: WebContext):
        self._ctx = context

    @abstractmethod
    def register(self, app: Flask) -> None:
        """Add this controller's routes to the Flask app."""

    @property
    def _user(self) -> User:
        return g.user

    @staticmethod
    def _field_errors(error: ValidationError) -> dict[str, str]:
        return error.field_errors

    def _job_or_404(self, job_id: str) -> Job:
        job = self._ctx.jobs.get_job(self._user.user_id, job_id)
        if job is None:
            abort(404)
        return job

    def _batch_or_404(self, batch_id: str) -> Batch:
        batch = self._ctx.jobs.get_batch(self._user.user_id, batch_id)
        if batch is None:
            abort(404)
        return batch

    def _ticked_products(self, batch: Batch, form) -> tuple[list[Product], dict[str, str]]:
        """Products from the label-check form for every photo the user kept ticked."""
        products, errors = [], {}
        for index, job in enumerate(batch.jobs):
            if job.status is not JobStatus.DONE or form.get(f"include_{index}") != "on":
                continue
            try:
                products.append(self._ctx.forms.product(form, prefix=f"p{index}_"))
            except ValidationError as error:
                errors.update(error.field_errors)
        return products, errors
