from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml

from runner import messages
from runner.exam_catalog import AmbiguousExamError, NoExamForPatientError
from runner.job import Job, JobState
from runner.job_runner import RESULT_DIR, run_job


@dataclass
class PipelineOutcome:
    """Result of run_pipeline.

    status "done"      -> pdf_path is set.
    status "suspended" -> job_id and checkpoint are set; the job waits for QC.
    """
    exam_id: str
    status: Literal["done", "suspended"]
    pdf_path: Path | None = None
    job_id: str | None = None
    checkpoint: str | None = None


def run_pipeline(
        report_generator, catalog, source_dir, acquisition_id, method_id,
        output_dir, series, exam_id=None, patient_name=None, exam_date=None, dev=False, qc=False,*, lang="en"
        ):
    if not exam_id :
        exams = catalog.find_exams(patient_name)
        matches = [e for e in exams if e.exam_date == exam_date]
        if len(matches) == 0:
            msg, hint = messages.no_exam_for_patient(patient_name, exam_date)
            raise NoExamForPatientError(msg, hint=hint)
        if len(matches) > 1:
            msg, hint = messages.ambiguous_exam(patient_name, exam_date, [e.exam_id for e in matches])
            raise AmbiguousExamError(msg, hint=hint)
        exam_id = matches[0].exam_id

    
    acquisition, seg_dict = next(iter(acquisition_id.items()))
    segment_name, side = next(iter(seg_dict.items()))

    method_name, other_params = next(iter(method_id.items()))
    if series:
        with open(Path(source_dir) / "series_selection.yml", "w") as f:
            yaml.dump(series, f)
    job = Job(source_dir=source_dir, exam_id=exam_id, segment=segment_name, method_id=method_name, series=series, other_params=other_params, exam_date=exam_date, qc = qc)
    run_job(job, dev)
    if job.state == JobState.SUSPENDED:
        return PipelineOutcome(
            exam_id=exam_id,
            status="suspended",
            job_id=job.job_id,
            checkpoint=job.checkpoint,
        )
    exam_ids_for_report = [exam_id]
    # if with_antecedent :
    #     related = catalog.find_related_exams(exam_id)
    #     if len(related) == 0 :
    #         raise ValueError(f"No prior exam of {exam_id}")
    #     most_recent = max(related, key=lambda e: e.exam_date)
                            
    #     exam_ids_for_report.append(most_recent.exam_id)
    pdf_path = report_generator.generate(exam_ids_for_report, RESULT_DIR, output_dir, lang=lang)
    return PipelineOutcome(
        exam_id=exam_id,
        status="done",
        pdf_path=pdf_path,
        job_id=job.job_id,
    )

