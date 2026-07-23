from abc import ABC, abstractmethod
from pathlib import Path



class ReportGenerationError(Exception):
    """Base class for all report generation failures."""


class NoResultsFoundError(ReportGenerationError):
    """Précondition : no results for the patient — nothing to generate."""
    def __init__(self, patient_id, data_dir):
        super().__init__(f"No results found for patient {patient_id} in {data_dir}")
        self.patient_id = patient_id
        self.data_dir = data_dir

class NoPDFGeneratedError(ReportGenerationError):
    """Postcondition : we tried to generate the PDF and it failed."""
    def __init__(self, patient_id, pdf_path):
        super().__init__(f"PDF generation failed: {pdf_path} was not created")
        self.patient_id = patient_id
        self.pdf_path = pdf_path


class ReportGenerator(ABC):
    @abstractmethod
    def generate(self, patient_id, data_dir, output_dir, *, lang="fr", config=None) -> Path:
        """Generate the patient's PDF from data_dir, write it under output_dir,
        and return the PDF path.

        Raises:
            NoResultsFoundError: no results available for this patient.
            NoPDFGeneratedError: generation ran but produced no PDF.
        """
        
        ...