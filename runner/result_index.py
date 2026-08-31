from abc import ABC, abstractmethod

from runner.errors import PipelineError

class ResultIndexError(PipelineError):
    """Base class for all result index failures."""

class ResultIndex(ABC):
    @abstractmethod
    def has_result(self, exam_id) -> bool:
        """True if a processed exam already exist for this exam_id."""
        ...