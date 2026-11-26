from pathlib import Path

from medical_report.interface.orchestrator import get_exam
from medical_report.section_generator.generate_pdf import OUTPUT_FILE, create_pdf
from adapters.patient_identity import PatientIdentityError, fetch_identity
from runner.qc_review import SectionFate, latest_validated, section_plan

from runner.report_generator import NoPDFGeneratedError, NoResultsFoundError, NoSectionAfterQCError, ReportGenerator
from adapters.file_qc_review_store import FileQCReviewStore

class MedicalReportGenerator(ReportGenerator):
    def __init__(self, identity_provider=fetch_identity, qc_store=None):
        self.identity_provider = identity_provider
        self.qc_store = qc_store if qc_store is not None else FileQCReviewStore()

    def generate(self, exam_ids, data_dir, output_dir, *, lang="en", config=None) -> Path:
        data_dir = Path(data_dir)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        antecedent_ids = exam_ids[1:]
        exams = get_exam(exam_ids[0], data_dir, config_data=config, antecedent_ids=antecedent_ids)
        if not exams:
            raise NoResultsFoundError(exam_ids[0], data_dir)
        exams, removed = self._apply_qc(exams)
        if removed:
            print(f"Warning: sections removed by the QC (not checked or rejected): {', '.join(removed)}")
        if not exams:
            raise NoSectionAfterQCError(exam_ids[0], removed)
        exam_date = exams[0].exam.metadata.exam_date
        try :
            identity = self.identity_provider(exam_ids[0], exam_date)
        except PatientIdentityError as error :
            identity = None
            print(f"Warning: patient identity not found ({error}). Fill in the name and birth date by hand in the report.")
        pdf_path = output_dir / OUTPUT_FILE
        pdf_path.unlink(missing_ok=True)
        create_pdf(exams, output_dir=output_dir, output_name=OUTPUT_FILE, lang=lang, patient_identity=identity)
        if not pdf_path.exists():
            raise NoPDFGeneratedError(exam_ids[0], pdf_path)

        return pdf_path

    def _qc_allows(self, exam_id, segment, method, job_id) -> bool:
        """True if the QC that counts for this block lets its section appear in the report.
        Only the QCs of the run that produced these results (same job_id) count."""
        qcs = self.qc_store.list_for_block(exam_id, segment, method)
        qcs = [qc for qc in qcs if qc.job_id == job_id]
        plan = section_plan(latest_validated(qcs))
        return plan.fate is SectionFate.SHOWN
    
    def _apply_qc(self, sections):
        """Keep the sections whose QC lets them appear, and in each one the antecedents whose QC lets them appear.
        Returns the kept sections and the names of the removed ones."""
        kept = []
        removed = []
        for section in sections:
            meta = section.exam.metadata
            if not self._qc_allows(meta.exam_id, meta.segment, meta.method, meta.job_id):
                removed.append(section.section_name)
                continue
            antecedents = []
            for antecedent in section.antecedents:
                ant_meta = antecedent.metadata
                if self._qc_allows(ant_meta.exam_id, ant_meta.segment, ant_meta.method, ant_meta.job_id):
                    antecedents.append(antecedent)
            section.antecedents = antecedents
            kept.append(section)
        return kept, removed

     # Un fichier du même nom peut déjà traîner dans output_dir (run précédent). On le
# supprime avant l'appel pour que "pdf_path.exists()" ci-dessous signifie bien
# "produit par cet appel", pas "un vieux fichier était déjà là".
# create_pdf avale ses propres exceptions (try/except interne qui imprime sur stdout
# sans relever) : si la génération échoue en interne, le NoPDFGeneratedError ci-dessous se
# déclenche bien, mais sans __cause__ vers l'erreur réelle — elle n'existe que dans
# la trace imprimée par create_pdf, perdue pour l'appelant.