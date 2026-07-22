import uuid

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


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
    segment: str
    method_id: str
    job_id: str = field(default_factory=_new_job_id)
    state: JobState = JobState.PENDING
    workdir: Path | None = None
