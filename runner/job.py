from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class JobState(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUSPENDED = "suspended"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class Job:
    job_id: str
    exam_id: str
    segment: str
    method_id: str
    state: JobState = JobState.PENDING
    workdir: Path | None = None

