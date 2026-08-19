from runner.job import Job 
from runner.job_runner import run_job, RESULT_DIR

def run_pipeline(
        result_index, retriever, report_generator, catalog, with_antecedent, dest_dir, mode, method,
        output_dir, segment, exam_id=None, patient_name=None, exam_date=None, *, lang="en", dev=False
        ):
    if not exam_id :
        exams = catalog.find_exams(patient_name)
        matches = [e for e in exams if e.exam_date == exam_date]
        if len(matches) != 1:
            raise ValueError(f"Expected exactly one exam for {patient_name} on {exam_date}, found {len(matches)}")
        #to do : indiquer les deux exam_id et inviter le user a refaire la recherche avec cette fois l'exam_id
        exam_id = matches[0].exam_id

    retriever.retrieve_exam(exam_id, dest_dir, mode=mode)
    segments = list(segment) if segment else ["legs", "thighs"]
    methods = list(method)
    for meth in methods: 
        for seg in segments:
            job = Job(exam_id=exam_id, segment=seg, method_id=meth)
            run_job(job, dev)
    exam_ids_for_report = [exam_id]
    if with_antecedent :
        related = catalog.find_related_exams(exam_id)
        if len(related) == 0 :
            raise ValueError(f"No prior exam of {exam_id}")
        most_recent = max(related, key=lambda e: e.exam_date)
        if not result_index.has_result(most_recent.exam_id):
            retriever.retrieve_exam(most_recent.exam_id, dest_dir, mode=mode)
            for meth in methods:
                for seg in segments :
                    job = Job(exam_id=most_recent.exam_id, segment=seg, method_id=meth)
                    run_job(job, dev)
        exam_ids_for_report.append(most_recent.exam_id)
    pdf_path = report_generator.generate(exam_ids_for_report, RESULT_DIR, output_dir, lang=lang)
    return {
        "exam_id": exam_id,
        "exam_ids_for_report": exam_ids_for_report,
        "pdf_path": pdf_path,
    }
