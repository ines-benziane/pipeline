from pathlib import Path

from medical_report.interface.orchestrator import get_exam
from medical_report.section_generator.generate_pdf import OUTPUT_FILE, create_pdf

from runner.report_generator import NoPDFGeneratedError, NoResultsFoundError, ReportGenerator


class MedicalReportGenerator(ReportGenerator):
    def generate(self, exam_ids, data_dir, output_dir, *, lang="en", config=None) -> Path:
        data_dir = Path(data_dir)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        antecedent_id = exam_ids[1] if len(exam_ids) > 1 else None
        exams = get_exam(exam_ids[0], data_dir, config_data=config, antecedent_id=antecedent_id)
        if not exams:
            raise NoResultsFoundError(exam_ids[0], data_dir)
        pdf_path = output_dir / OUTPUT_FILE
        pdf_path.unlink(missing_ok=True)
        create_pdf(exams, output_dir=output_dir, output_name=OUTPUT_FILE, lang=lang)
        if not pdf_path.exists():
            raise NoPDFGeneratedError(exam_ids[0], pdf_path)

        return pdf_path



     # Un fichier du même nom peut déjà traîner dans output_dir (run précédent). On le
# supprime avant l'appel pour que "pdf_path.exists()" ci-dessous signifie bien
# "produit par cet appel", pas "un vieux fichier était déjà là".
# create_pdf avale ses propres exceptions (try/except interne qui imprime sur stdout
# sans relever) : si la génération échoue en interne, le NoPDFGeneratedError ci-dessous se
# déclenche bien, mais sans __cause__ vers l'erreur réelle — elle n'existe que dans
# la trace imprimée par create_pdf, perdue pour l'appelant.