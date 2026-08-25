"""Run job, manage its state. 
If SUCCESS : save the final result file (JSON file used by medical_report).
If any exception raised : job's state becomes FAILED --Later : and the crash mode is activated. 
"""

import shutil
import logging
from pathlib import Path

from runner import job_store, methods_registry
from runner.job import JobState

WORKDIR_ROOT = Path("workdirs")
RESULT_DIR = Path("data") / "results"

def make_workdir(job_id: str) -> Path:
    workdir = WORKDIR_ROOT / job_id
    workdir.mkdir(parents=True, exist_ok=True)
    return workdir 

def run_job(job, dev=False) :
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
    try:
        result = method.run(job.exam_dir, job.exam_id, job.workdir, job.segment, job.series, job.other_params)
        
    except Exception:
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
    return job


if __name__ == "__main__":
    from methods.dummy import DummyMethod
    from runner.job import Job
    methods_registry.register(DummyMethod)
    job = Job( exam_dir="dest_dir", exam_id="exam_bidon", segment="legs", method_id="dummy")
    run_job(job)
    print(job)
