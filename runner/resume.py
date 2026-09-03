from runner.job import Job
from runner.job_runner import run_job
from runner.method import Result, QCUserDecisions


def resume_pipeline(job_id, decision_status, output_dir, state, exam_id, segment,
                    method_id, workdir, checkpoint, qc, source_dir, series, tag,
                    comment, debug=False, action=None):
    """Re-run the same job (same job_id) after a QC pause.

    Without `action`: continue from `checkpoint` via handle_checkpoint.
    With `action`: clear `checkpoint` and re-run from scratch with the correction applied.
    """
    decision = QCUserDecisions(
        decision_status=decision_status,
        tag=tag, 
        comment=comment,
        action=action
    )
    job = Job(job_id=job_id, workdir=workdir, source_dir=source_dir, exam_id=exam_id, segment=segment,
              method_id=method_id, series=series, qc="checkpoint" if qc else "off", checkpoint=checkpoint)
    if action:
        job.checkpoint=None
    #TO DO : insérer le vrai dev si ya un mode dev dans resume.. a réfléchir
    return run_job(job, output_dir, debug=debug, decision=decision, action=action)
