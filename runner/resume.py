import json
from pathlib import Path

from runner import job_store, methods_registry
from runner.job import JobState, Job
from runner.job_runner import run_job
from runner.method import Result

from mutools.io import volume


def resume_pipeline(job_id, decision, state, exam_id, segment, method_id, workdir, checkpoint, qc, source_dir, series):
    """Resume where the job stopped. After mutools or after segmentation. Creates a new job and sends it to the pipeline 
    at the right place
    """
    
    job = Job(job_id=job_id, workdir=workdir, source_dir=source_dir, exam_id=exam_id, segment=segment, method_id=method_id, series=series, qc = qc, checkpoint = checkpoint)
    return run_job(job)
