from runner import job_store
from runner.job_runner import run_job
from runner.method import QCUserDecisions


def resume_pipeline(job_id, output_dir, decision_status, qc,
                    tag=None, comment=None, debug=False, action=None):
    """Re-run the same job (same job_id) after a QC pause.

    Without `action`: continue from `job.checkpoint` via handle_checkpoint.
    With `action`: clear `checkpoint` and re-run from scratch with the correction applied.

    The job is loaded from the internal store by id; the user never handles the job file.
    """
    job = job_store.load(job_id)
    job.qc = "checkpoint" if qc else "off"
    if action:
        job.checkpoint = None

    decision = QCUserDecisions(
        decision_status=decision_status,
        tag=tag,
        comment=comment,
        action=action,
    )
    return run_job(job, output_dir, debug=debug, decision=decision, action=action)
