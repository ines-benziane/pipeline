from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

from runner.errors import PipelineError

class ExamRetrieverError(PipelineError):
    """Base class for all retrieval failures."""

class ExamNotFoundError(ExamRetrieverError):
    """No results for the exam."""
    def __init__(self, exam_id):
        super().__init__(f"No results found for exam_id {exam_id}")
        self.exam_id = exam_id

class SourceUnavailableError(ExamRetrieverError):
    """The exam data could not be reached - nothing to retrieve"""
    def __init__(self, reason):
        super().__init__(f"Unavailable source : {reason}")
        self.reason = reason 

class IncompleteRetrievalError(ExamRetrieverError):
    """Exam retrieval incomplete."""
    def __init__(self, expected_series, received_series):
        super().__init__(f"Incomplete retrieval. Expected series: {len(expected_series)}. Received series : {len(received_series)}")
        self.expected_series = expected_series 
        self.received_series = received_series 

class DeidentificationError(ExamRetrieverError):
    """Deidentification failed"""
    def __init__(self, reason):
        super().__init__(f"De-identification fails : {reason}")
        self.reason = reason 

class DeidentificationMode(Enum):
    ANONYMIZE = "anonymize"
    PSEUDONYMIZE = "pseudonymize"

@dataclass 
class RetrievedSeries():
    """Show the retrieved series: id, number of files, directory"""
    series_id : str
    number_of_files : int
    series_directory : str
    
@dataclass
class ExamRetrievalResult():
    """Show the result of retrieve_exam : exam_id, directory destination, list of series retrieved, 
    de-identification mode, date and time"""
    exam_id : str
    destination_dir : str
    series_retrieved : list[RetrievedSeries]
    deidentification_mode : DeidentificationMode
    time : datetime

class ExamRetriever(ABC):
    @abstractmethod
    def retrieve_exam(self, exam_id, destination_dir, *, mode, config=None) -> ExamRetrievalResult :
        """
        Retrieve exam's series, deidentifie, writes in destination_dir.

        Raises:
            ExamNotFoundError: exam_id does not match any known exam.
            SourceUnavailableError: the exam data could not be reached.
            IncompleteRetrievalError: some expected series were not received.
            DeidentificationError: de-identification failed for at least one file.
        """
        ...
