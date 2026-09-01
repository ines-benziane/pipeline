from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal

@dataclass
class Result :
    results : dict
    auto_valid : bool
    provenance : dict

class QCCheckpoint(Exception):
    """Signal raised by a method to suspend a job for quality control.
    Not a PipelineError: this is not a failure.

    `name` identifies the stage the method paused at. The method owns the
    set of valid names; the runner only stores it back on the job.
    """
    def __init__(self, name: str):
        super().__init__(f"Job suspended at checkpoint {name!r} for QC")
        self.name = name

@dataclass
class QCUserDecisions:
    """ 3 information from the user that will be injected in the result file."""
    decision_status: Literal["yes", "no", "pending"]
    tag: Literal["swap", "muscle_off"] | None = None
    comment: str | None = None


class Method (ABC): 
    name : str
    version : str
    comparability_criteria : list

    @abstractmethod
    def run(self, source_dir, exam_id, workdir, segment, series, params, date, qc, qc_dir, decision=None):
        ...

    @abstractmethod
    def handle_checkpoint(self, *, name, workdir, segment, exam_id, qc, decision=None):
        ... 