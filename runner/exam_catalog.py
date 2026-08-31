from abc import ABC, abstractmethod
from dataclasses import dataclass

from runner.errors import PipelineError


class ExamCatalogError(PipelineError):
    """Base class for all cataloging failures."""


class ExamNotFoundError(ExamCatalogError):
    """No results for the exam."""
    def __init__(self, exam_id):
        super().__init__(f"No results found for exam_id {exam_id}")
        self.exam_id = exam_id

class SourceUnavailableError(ExamCatalogError):
    """The imaging data source could not be reached - nothing to look up"""
    def __init__(self, reason):
        super().__init__(f"Unavailable source : {reason}")
        self.reason = reason

class NoExamForPatientError(ExamCatalogError):
    """No exam matches the given patient name and date."""

class AmbiguousExamError(ExamCatalogError):
    """Several exams match the given patient name and date."""

@dataclass
class ExamSummary():
    exam_id : str
    patient_name : str
    exam_date : str
    description : str


@dataclass
class SeriesSummary():
    description : str
    series_id : str


class ExamCatalog(ABC):
    @abstractmethod
    def find_exams(self, patient_name) -> list[ExamSummary]:
        """Takes a patient's name. Returns a list of exams
        """
        ...
    @abstractmethod
    def find_related_exams(self, exam_id) -> list[ExamSummary]:
        """Takes an exam ID. Returns a list of exams from the same patient"""
        ...
    @abstractmethod
    def show_series(self, exam_id) -> list[SeriesSummary]:
        """Takes an exam_ID. Returns a list of the series it contains"""