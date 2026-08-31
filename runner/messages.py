"""User-facing message text for the pipeline.

"""


def ambiguous_exam(patient_name, exam_date, candidate_ids):
    """Several exams match a patient name + date; the caller must disambiguate."""
    ids = ", ".join(candidate_ids)
    message = f"{len(candidate_ids)} exams match {patient_name!r} on {exam_date}: {ids}"
    hint = f"rerun with --exam-id set to one of: {ids}"
    return message, hint


def no_exam_for_patient(patient_name, exam_date):
    """No exam matches the given patient name + date."""
    message = f"no exam for {patient_name!r} on {exam_date}"
    hint = "check the patient name and date, or pass --exam-id directly"
    return message, hint
