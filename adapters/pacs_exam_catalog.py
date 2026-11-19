# PacsExamCatalog(ExamCatalog)
#   __init__(finder)                  → le Find à utiliser (un faux dans les tests)
#   find_related_exams(exam_id):
#      1. C-FIND STUDY sur patient_id=exam_id      → nom + date de naissance (bruts, avec ^)
#         aucun résultat     → ExamNotFoundError (existe déjà dans runner/exam_catalog.py)
#         identités différentes → AmbiguousExamError (existe aussi)
#      2. C-FIND STUDY sur patient_name=ce nom brut → toutes les études de ce nom
#      3. garder celles qui ont la même date de naissance, sauf l'examen lui-même
#      4. un ExamSummary par identifiant d'examen (un examen peut être stocké en plusieurs études)
#   find_exams, show_series           → NotImplementedError pour l'instant (obligatoires car abstraites)

from dicom.config.server_config import TelemisConfig
from dicom.services.find import Find
from dicom.services.search_criteria import SearchCriteria
from runner.exam_catalog import AmbiguousExamError, ExamCatalog, ExamNotFoundError, ExamSummary


class PacsExamCatalog(ExamCatalog):
    def __init__(self, finder=None):
        self.finder = finder or Find(TelemisConfig)

    def find_exams(self, patient_name):
        raise NotImplementedError("find_exams: not implemented yet for the PACS")

    def show_series(self, exam_id):
        raise NotImplementedError("show_series: not implemented yet for the PACS")

    def find_related_exams(self, exam_id):
        """Other exams of the same patient (same name AND same birth date on the PACS), oldest first.
        The exam itself is not in the list. Error messages never contain the patient's name."""
        # 1. identity of the exam
        studies = self.finder.search_data(SearchCriteria(level="STUDY", patient_id=exam_id))
        if not studies:
            raise ExamNotFoundError(exam_id)   # also when the PACS is unreachable: Find returns [] in both cases
        identities = {_identity(ds) for ds in studies}
        if len(identities) > 1:
            raise AmbiguousExamError(f"{exam_id}: {len(identities)} different identities on the PACS")
        identity = identities.pop()
        name = str(studies[0].PatientName).strip()
        # an empty name in a C-FIND matches EVERY patient: never search with it
        if not identity[0] or not identity[1]:
            raise AmbiguousExamError(f"{exam_id}: no name or no birth date on the PACS, related exams cannot be searched",
                                     hint="give the earlier exam IDs by hand")

        # 2. every study with this name; 3. same name and birth date, other exam
        related = {}
        for ds in self.finder.search_data(SearchCriteria(level="STUDY", patient_name=name)):
            other_id = str(ds.PatientID)
            if _identity(ds) != identity or other_id == exam_id:
                continue
            # 4. one exam can be stored as several studies: keep one summary per exam ID
            if other_id not in related:
                related[other_id] = ExamSummary(
                    exam_id=other_id,
                    patient_name=name.replace("^", " ").strip(),
                    exam_date=_iso_date(str(ds.get("StudyDate", ""))),
                    description=str(ds.get("StudyDescription", "")),
                )
        return sorted(related.values(), key=lambda exam: exam.exam_date)


def _identity(ds):
    """(name, birth date) compared case-insensitively: the PACS matches names regardless of case,
    and the same patient can be stored "DOE^JANE" in one exam and "Doe^Jane" in another."""
    return str(ds.PatientName).strip().casefold(), str(ds.PatientBirthDate).strip()


def _iso_date(dicom_date):
    """DICOM "20260112" -> "2026-01-12", the format of exam_date in the JSON results."""
    if len(dicom_date) == 8:
        return f"{dicom_date[0:4]}-{dicom_date[4:6]}-{dicom_date[6:8]}"
    return dicom_date
