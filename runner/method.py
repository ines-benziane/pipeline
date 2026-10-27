from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from mutools.io import volume
import logging
log = logging.getLogger(__name__)

@dataclass
class Result :
    results : Path
    auto_valid : bool
    provenance : dict

class QCCheckpoint(Exception):
    """Signal raised by a method to suspend a job for quality control.

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
    action: str | None = None

@dataclass(frozen=True)
class RunContext:
    """Everything a method needs for one run, built by the runner from the job.
    Frozen: a method that needs different values (e.g. t2map calling dixon3pt)
    makes a copy with dataclasses.replace instead of changing the caller's context."""
    source_dir : str
    exam_id : str
    workdir : Path
    segment : str
    series : list[int]
    qc : str = "off"
    params : dict | None = None
    exam_date : str | None = None
    qc_dir : Path | None = None
    decision : QCUserDecisions | None = None
    debug : bool = False
    action : str | None = None
    multicenter : bool = False
    seg_series : list[int] | None = None

class Method (ABC):
    name : str
    version : str
    comparability_criteria : list
    CHECKPOINTS: tuple[str, ...] = ()
    ACTIONS: tuple[str, ...] = ()
    @abstractmethod
    def run(self, ctx: RunContext) -> Result:
        """Run the method on one exam described by `ctx`; return its result file."""
        ...

    @abstractmethod
    def handle_checkpoint(self, *, name, workdir, segment, exam_id, qc, qc_dir=None, decision=None, debug=False, multicenter=False,
                          seg_series=None):
        ...

    def _check_checkpoint(self, name):
        if name not in self.CHECKPOINTS:
            raise ValueError(f"{name!r} not a checkpoint of {self.name}: {self.CHECKPOINTS}")

    def _check_action(self, name):
        if name is not None and name not in self.ACTIONS:
            raise ValueError(f"{name!r} not an action of {self.name}: {self.ACTIONS}")

    def _dump_crash(self, workdir, **arrays):
        """Best-effort dump of in-memory volumes to workdir/crash/ when a stage
        raises under --debug. Write failures are logged, never re-raised."""
        crash_dir = Path(workdir) / "crash"
        try:
            crash_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            log.warning("crash dump: could not create %s", crash_dir, exc_info=True)
            return
        for label, arr in arrays.items():
            try:
                volume.write(crash_dir / f"{label}.mha", arr)
            except Exception:
                log.warning("crash dump: could not write %s", label, exc_info=True)

