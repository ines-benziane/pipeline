from runner.job import Job
from runner.job_runner import run_job
from runner.method import Result, QCUserDecisions


def resume_pipeline(job_id, decision_status, state, exam_id, segment, method_id, workdir, checkpoint, qc, source_dir, series, tag, comment):
    """Resume where the job stopped. After mutools or after segmentation. Creates a new job and sends it to the pipeline 
    at the right place
    """
    decision = QCUserDecisions(
        decision_status=decision_status,
        tag=tag, 
        comment=comment
    )
    job = Job(job_id=job_id, workdir=workdir, source_dir=source_dir, exam_id=exam_id, segment=segment,
              method_id=method_id, series=series, qc="checkpoint" if qc else "off", checkpoint=checkpoint)
    #TO DO : insérer le vrai dev si ya un mode dev dans resume.. a réfléchir
    return run_job(job, decision=decision)
