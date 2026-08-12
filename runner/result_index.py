from abc import ABC, abstractmethod

class ResultIndexError(Exception):
    """Base class for all result index failures."""

class ResultIndex(ABC):
    @abstractmethod
    def has_result(self, exam_id) -> bool:
        """True if a processed exam already exist for this exam_id."""
        ...