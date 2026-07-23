from pathlib import Path

from medical_report.interface.orchestrator import get_exam
from medical_report.section_generator.generate_pdf import OUTPUT_FILE, create_pdf

from runner.report_generator import NoPDFGeneratedError, NoResultsFoundError, ReportGenerator


class MedicalReportGenerator(ReportGenerator):
    def generate(self, patient_id, data_dir, output_dir, *, lang="fr", config=None) -> Path:
        data_dir = Path(data_dir)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        exams = get_exam(patient_id, data_dir, config_data=config)
        if not exams:
            raise NoResultsFoundError(patient_id, data_dir)
        pdf_path = output_dir / OUTPUT_FILE
        # Un fichier du même nom peut déjà traîner dans output_dir (run précédent). On le
        # supprime avant l'appel pour que "pdf_path.exists()" ci-dessous signifie bien
        # "produit par cet appel", pas "un vieux fichier était déjà là".
        pdf_path.unlink(missing_ok=True)
        # create_pdf avale ses propres exceptions (try/except interne qui imprime sur stdout
        # sans relever) : si la génération échoue en interne, le NoPDFGeneratedError ci-dessous se
        # déclenche bien, mais sans __cause__ vers l'erreur réelle — elle n'existe que dans
        # la trace imprimée par create_pdf, perdue pour l'appelant.
        create_pdf(exams, output_dir=output_dir, output_name=OUTPUT_FILE, lang=lang)
        if not pdf_path.exists():
            raise NoPDFGeneratedError(patient_id, pdf_path)

        return pdf_path
