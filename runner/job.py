"""Jobs tracks the state of a single task going through the "methods" brick.
It will be useful for reporting to a server, once one exists.
It let us tell a failed task apart from one that is normally suspended for QC,
and weither a task can be resumed or not."""

import uuid

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from datetime import datetime


class JobState(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUSPENDED = "suspended"
    RESULTS_READY = "results_ready"
    FAILED = "failed"

def _new_job_id() -> str:
    return f"{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:4]}"

@dataclass
class Job:
    exam_id: str
    source_dir: str
    segment: str
    method_id: str
    series: list[int]
    state: JobState = JobState.PENDING
    job_id: str | None = None
    workdir: Path | None = None
    other_params:  list[str] | None = None
    exam_date: str | None = None 
    qc: str | None = "off"
    checkpoint: str | None = None
    qc_dir: Path | None = None

    def __post_init__(self):
        if self.job_id is None:
            self.job_id = f"{self.exam_id}-{_new_job_id()}"
        if self.qc not in ("off", "checkpoint", "global"):
            raise ValueError(f"qc must be off/checkpoint/global, got {self.qc!r}")