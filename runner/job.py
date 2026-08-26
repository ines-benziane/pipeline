"""Jobs tracks the state of a single task going through the "methods" brick.
It will be useful for reporting to a server, once one exists.
It let us tell a failed task apart from one that is normally suspended for QC,
and weither a task can be resumed or not."""

import uuid

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class JobException(Exception):
    """Base class for raising Job exception that indicates Job's state"""

class QCMutoolsException(JobException):
    """Job purposely suspended to do the QC"""
    def __init__(self):
        super().__init__(f"Job suspended after mutools for QC")


class QCMuSegAIException(JobException):
    """Job purposely suspended to do the QC"""
    def __init__(self):
        super().__init__(f"Job suspended after automatique segmentation for QC")


class JobState(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUSPENDED = "suspended"
    RESULTS_READY = "results_ready"
    FAILED = "failed"

def _new_job_id() -> str:
    return uuid.uuid4().hex[:6]

@dataclass
class Job:
    exam_id: str
    source_dir: str
    segment: str
    method_id: str
    series: list[int]
    job_id: str = field(default_factory=_new_job_id)
    state: JobState = JobState.PENDING
    workdir: Path | None = None
    other_params:  list[str] | None = None
    exam_date: str | None = None 
    qc: bool | None = False
    checkpoint: str | None = None

