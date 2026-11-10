import logging

from .job_observer import JobObserver
from .job import Job

logger = logging.getLogger("nutrilenz.jobs")


class JobLogger(JobObserver):
    """Writes job progress to the log file."""

    def on_job_update(self, job: "Job") -> None:
        logger.info("job %s (%s) %s: %s", job.job_id[:8], job.kind, job.status.value, job.step)
