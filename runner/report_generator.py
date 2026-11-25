from abc import ABC, abstractmethod
from pathlib import Path

from runner.errors import PipelineError


class ReportGenerationError(PipelineError):
    """Base class for all report generation failures."""


class NoResultsFoundError(ReportGenerationError):
    """Précondition : no results for the exam — nothing to generate."""
    def __init__(self, exam_id, data_dir):
        super().__init__(f"No results found for exam {exam_id} in {data_dir}")
        self.exam_id = exam_id
        self.data_dir = data_dir

class NoSectionAfterQCError(ReportGenerationError):
    """No section of the exam has a validated QC that lets it appear: no report."""
    def __init__(self, exam_id, removed):
        super().__init__(f"No section of exam {exam_id} passed the QC (removed: {', '.join(removed)})",
                         hint="validate the QC of the exam in the QC window, then generate the report again")
        self.exam_id = exam_id
        self.removed = removed

class NoPDFGeneratedError(ReportGenerationError):
    """Postcondition : we tried to generate the PDF and it failed."""
    def __init__(self, exam_id, pdf_path):
        super().__init__(f"PDF generation failed: {pdf_path} was not created")
        self.exam_id = exam_id
        self.pdf_path = pdf_path


class ReportGenerator(ABC):
    @abstractmethod
    def generate(self, exam_ids, data_dir, output_dir, *, lang="en", config=None) -> Path:
        """Generate the exam's PDF from data_dir, write it under output_dir,
        and return the PDF path.

        Raises:
            NoResultsFoundError: no results available for this exam.
            NoPDFGeneratedError: generation ran but produced no PDF.
        """
        
        ...