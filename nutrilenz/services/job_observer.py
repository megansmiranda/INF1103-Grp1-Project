from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .job import Job


class JobObserver(ABC):
    """Interface for anything that wants to hear when a job changes."""

    @abstractmethod
    def on_job_update(self, job: "Job") -> None:
        """Called after every status or step change."""
