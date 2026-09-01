"""Run job, manage its state. 
If SUCCESS : save the final result file (JSON file used by medical_report).
If any exception raised : job's state becomes FAILED --Later : and the crash mode is activated. 
"""

import shutil
import logging
import json
from pathlib import Path

from mutools.io import volume
from mutools import io

from runner.method import Result, QCCheckpoint
from runner import job_store, methods_registry
from runner.job import JobState
from runner.progress import announce

WORKDIR_ROOT = Path("workdirs")
RESULT_DIR = Path("data") / "results"
QC_DIR = Path("data") / "qc"

log = logging.getLogger(__name__)

def make_workdir(job_id: str) -> Path:
    workdir = WORKDIR_ROOT / job_id
    workdir.mkdir(parents=True, exist_ok=True)
    return workdir 

def make_qc_dir(job_id: str) -> Path:
    qc_dir = QC_DIR / job_id
    qc_dir.mkdir(parents=True, exist_ok=True)
    return qc_dir

def run_job(job, dev=False, decision=None) :
    method = methods_registry.get(job.method_id) #retrieve the method asked
    job.workdir = make_workdir(job.job_id)       #creates a workdir to store job's trace
    job.state = JobState.IN_PROGRESS             #changes job status 
    log_path = job.workdir / "run.log"
    handler = logging.FileHandler(log_path)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    handler.setLevel(logging.DEBUG if dev else logging.INFO)
    root_logger = logging.getLogger()
    previous_level = root_logger.level
    root_logger.setLevel(logging.DEBUG if dev else logging.INFO)
    root_logger.addHandler(handler)
    # quiets noisy third-party libraries even in dev mode (docker/urllib3 log
    # every HTTP call to the docker daemon at DEBUG level)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("docker").setLevel(logging.WARNING)

    job_store.save(job)
    announce(f"Task {job.job_id} started - {job.method_id} / {job.segment}")
    if job.qc_dir is None:
        job.qc_dir = make_qc_dir(job.job_id)
    try:
        if job.checkpoint:
            result = method.handle_checkpoint(name=job.checkpoint, workdir=job.workdir, segment=job.segment, exam_id=job.exam_id, qc=job.qc, decision=decision)
        else:
            result = method.run(job.source_dir, job.exam_id, job.workdir, job.segment, job.series, job.other_params, job.exam_date, job.qc, job.qc_dir, decision)

    except QCCheckpoint as e:
        log.info("job %s suspended for QC (%s)", job.job_id, e)
        announce(f"Task {job.job_id} paused for QC (checkpoint: {e.name})")
        job.state = JobState.SUSPENDED
        job.checkpoint = e.name
        job_store.save(job)
        return(job)

    except Exception:
        announce(f"Task {job.job_id} failed")
        job.state = JobState.FAILED
        job_store.save(job)
        raise
    finally :
        root_logger.removeHandler(handler)
        root_logger.setLevel(previous_level)
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy(result.results, RESULT_DIR / result.results.name) #results given by method (ex json_output)
    if result.auto_valid: #not implemented yet
        job.state = JobState.RESULTS_READY
    else :
        job.state = JobState.SUSPENDED
    job_store.save(job)
    announce(f"Task {job.job_id} done - {result.results.name}")
    return job
