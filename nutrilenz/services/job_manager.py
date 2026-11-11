import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from .job_observer import JobObserver
from .job_logger import JobLogger
from .job import Job
from .batch import Batch


class JobManager:
    """Runs jobs on a small thread pool. The pool size also limits how many
    AI calls run at once, which keeps us under the API rate limit."""

    KEEP_SECONDS = 3600

    def __init__(self, workers: int = 3, observers: list[JobObserver] | None = None):
        self._pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="nutrilenz-job")
        self._observers = list(observers) if observers is not None else [JobLogger()]
        self._jobs: dict[str, Job] = {}
        self._batches: dict[str, Batch] = {}
        self._lock = threading.Lock()

    def submit(self, owner_id: int, kind: str, work: Callable[[Job], object]) -> Job:
        job = Job(owner_id, kind, self._observers)
        with self._lock:
            self._forget_old_jobs()
            self._jobs[job.job_id] = job
        self._pool.submit(job.run, work)
        return job

    def submit_batch(self, owner_id: int, kind: str,
                     works: list[Callable[[Job], object]]) -> Batch:
        batch = Batch(owner_id, [self.submit(owner_id, kind, work) for work in works])
        with self._lock:
            self._batches[batch.batch_id] = batch
        return batch

    def get_job(self, owner_id: int, job_id: str) -> Job | None:
        """Users can only see their own jobs."""
        with self._lock:
            job = self._jobs.get(job_id)
        return job if job is not None and job.owner_id == owner_id else None

    def get_batch(self, owner_id: int, batch_id: str) -> Batch | None:
        with self._lock:
            batch = self._batches.get(batch_id)
        return batch if batch is not None and batch.owner_id == owner_id else None

    def _forget_old_jobs(self) -> None:
        old = [key for key, job in self._jobs.items()
               if job.finished and job.age_seconds > self.KEEP_SECONDS]
        for key in old:
            del self._jobs[key]
        self._batches = {key: batch for key, batch in self._batches.items()
                         if any(job.job_id in self._jobs for job in batch.jobs)}

    def shutdown(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)
