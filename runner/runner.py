import shutil
from pathlib import Path

from runner import methods_registry
from runner.job import JobState

WORKDIR_ROOT = Path("workdirs")
RESULT_DIR = Path("data") / "results"

def make_workdir(job_id: str) -> Path:
    workdir = WORKDIR_ROOT / job_id
    workdir.mkdir(parents=True, exist_ok=True)
    return workdir 

def run_pipeline(job) :
    method = methods_registry.get(job.method_id)
    job.state = JobState.IN_PROGRESS
    job.workdir = make_workdir(job.job_id)
    try:
        result = method.run(job.exam_id, job.workdir, job.segment)
    except Exception: 
        job.state = JobState.FAILED
        raise
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy(result.results, RESULT_DIR / result.results.name)
    if result.auto_valid: 
        job.state = JobState.COMPLETED
    else : 
        job.state = JobState.SUSPENDED
    return job
        

if __name__ == "__main__":
    from methods.dummy import DummyMethod
    from runner.job import Job
    methods_registry.register(DummyMethod)
    job = Job(job_id="j001", exam_id="exam_bidon", segment="legs", method_id="dummy")
    run_pipeline(job)
    print(job)
