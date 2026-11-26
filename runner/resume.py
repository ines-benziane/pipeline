from dataclasses import replace

from runner import job_store
from runner.job_runner import run_job
from runner.method import QCUserDecisions


def resume_pipeline(job_id, output_dir, decision_status, qc,
                    tag=None, comment=None, debug=False, action=None):
    """Go on with a job after a QC pause.

    Without `action`: same job (same job_id), continues from `job.checkpoint` via handle_checkpoint.
    With `action`: a new job (new job_id) re-runs from scratch with the correction applied;
    the suspended job and its folders are left untouched.

    The job is loaded from the internal store by id; the user never handles the job file.
    """
    job = job_store.load(job_id)
    job.qc = "checkpoint" if qc else "off"
    if action:
        # a correction computes new results: new run (new job_id, new folders), the earlier run is kept as it was
        job = replace(job, job_id=None, checkpoint=None, workdir=None, qc_dir=None)

    decision = QCUserDecisions(
        decision_status=decision_status,
        tag=tag,
        comment=comment,
        action=action,
    )
    return run_job(job, output_dir, debug=debug, decision=decision, action=action)
