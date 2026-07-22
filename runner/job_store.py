import json
from pathlib import Path

from runner.job import Job, JobState

JOBS_DIR = Path("data") / "jobs"

def save(job):
    JOBS_DIR.mkdir(parents=True, exist_ok=True)

    data = {
        "job_id": job.job_id,
        "exam_id": job.exam_id,
        "segment": job.segment,
        "method_id": job.method_id,
        "state": job.state.value,
        "workdir": str(job.workdir) if job.workdir else None, 
    }

    path = JOBS_DIR / f"{job.job_id}.json"
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")

def load(job_id):
    path = JOBS_DIR / f"{job_id}.json"
    if not path.exists():
        raise KeyError(f"Unknown job: {job_id}")
    
    data = json.loads(path.read_text(encoding="utf-8"))

    return Job(
        job_id = data["job_id"],
        exam_id=data["exam_id"],
        segment=data["segment"],
        method_id=data["method_id"],
        state=JobState(data["state"]),
        workdir=Path(data["workdir"]) if data["workdir"] else None,
    )