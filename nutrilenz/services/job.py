from __future__ import annotations

import logging
import threading
import time
import uuid
from typing import Callable, TYPE_CHECKING

from ..errors.nutrilenz_error import NutriLenzError
from .job_status import JobStatus

if TYPE_CHECKING:
    from .job_observer import JobObserver

logger = logging.getLogger("nutrilenz.jobs")


class Job:
    """One piece of slow work (AI calls) running on a background thread.
    The web page polls it so the user never waits on a frozen page."""

    def __init__(self, owner_id: int, kind: str, observers: list[JobObserver]):
        self._job_id = uuid.uuid4().hex
        self._owner_id = owner_id
        self._kind = kind
        self._status = JobStatus.QUEUED
        self._step = "Waiting to start"
        self._result = None
        self._error_code: str | None = None
        self._created = time.monotonic()
        self._observers = list(observers)
        self._lock = threading.Lock()

    @property
    def job_id(self) -> str:
        return self._job_id

    @property
    def owner_id(self) -> int:
        return self._owner_id

    @property
    def kind(self) -> str:
        return self._kind

    @property
    def status(self) -> JobStatus:
        return self._status

    @property
    def step(self) -> str:
        return self._step

    @property
    def result(self):
        return self._result

    @property
    def error_code(self) -> str | None:
        return self._error_code

    @property
    def age_seconds(self) -> float:
        return time.monotonic() - self._created

    @property
    def finished(self) -> bool:
        return self._status in (JobStatus.DONE, JobStatus.FAILED)

    def set_step(self, step: str) -> None:
        self._update(status=JobStatus.RUNNING, step=step)

    def _update(self, **changes) -> None:
        with self._lock:
            for name, value in changes.items():
                setattr(self, "_" + name, value)
        for observer in self._observers:
            observer.on_job_update(self)

    def run(self, work: Callable[["Job"], object]) -> None:
        """Called on a worker thread. Errors never escape: they mark the job FAILED."""
        self._update(status=JobStatus.RUNNING, step="Starting")
        try:
            result = work(self)
        except NutriLenzError as error:
            self._update(status=JobStatus.FAILED, step="Failed", error_code=error.code)
        except Exception:
            logger.exception("Unexpected error in job %s", self._job_id)
            self._update(status=JobStatus.FAILED, step="Failed", error_code="UNEXPECTED_ERROR")
        else:
            self._update(status=JobStatus.DONE, step="Done", result=result)
