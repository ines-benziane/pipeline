import shutil
from pathlib import Path

from runner import job_store, methods_registry
from runner.job import JobState

WORKDIR_ROOT = Path("workdirs")
RESULT_DIR = Path("data") / "results"

def make_workdir(job_id: str) -> Path:
    workdir = WORKDIR_ROOT / job_id
    workdir.mkdir(parents=True, exist_ok=True)
    return workdir 

def run_job(job) :
    method = methods_registry.get(job.method_id) #retrieve the method asked
    job.state = JobState.IN_PROGRESS             #changes job status 
    job.workdir = make_workdir(job.job_id)       #creates a workdir to store job's trace
    job_store.save(job)
    try:
        result = method.run(job.exam_id, job.workdir, job.segment)
    except Exception:
        job.state = JobState.FAILED
        job_store.save(job)
        raise
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy(result.results, RESULT_DIR / result.results.name) #results given by method (ex json_output)
    if result.auto_valid: 
        job.state = JobState.RESULTS_READY
    else : 
        job.state = JobState.SUSPENDED
    job_store.save(job)
    return job
        

if __name__ == "__main__":
    from methods.dummy import DummyMethod
    from runner.job import Job
    methods_registry.register(DummyMethod)
    job = Job( exam_id="exam_bidon", segment="legs", method_id="dummy")
    run_job(job)
    print(job)
