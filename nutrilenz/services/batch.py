import uuid

from .job_status import JobStatus
from .job import Job


class Batch:
    """A group of jobs started together (e.g. several label photos).
    It only refers to jobs; the JobManager owns them (aggregation)."""

    def __init__(self, owner_id: int, jobs: list[Job]):
        self._batch_id = uuid.uuid4().hex
        self._owner_id = owner_id
        self._jobs = list(jobs)

    @property
    def batch_id(self) -> str:
        return self._batch_id

    @property
    def owner_id(self) -> int:
        return self._owner_id

    @property
    def jobs(self) -> tuple[Job, ...]:
        return tuple(self._jobs)

    @property
    def finished(self) -> bool:
        return all(job.finished for job in self._jobs)

    def count(self, status: JobStatus) -> int:
        return sum(1 for job in self._jobs if job.status is status)

    @property
    def done_count(self) -> int:
        return self.count(JobStatus.DONE)
