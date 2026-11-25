"""Port QCReviewStore: what can be asked to a store of QC reviews (save one, list those of a block),
without saying where they are kept. The window and the report generator only know this port."""

from abc import ABC, abstractmethod

from runner.errors import PipelineError
from runner.qc_review import QCReview


class QCReviewStoreError(PipelineError):
    """A QC review could not be saved or read back."""


class QCReviewStore(ABC):
    @abstractmethod
    def save(self, qc: QCReview) -> None:
        """Keep the QC. Saving again a QC with the same qc_id replaces it."""
        ...

    @abstractmethod
    def list_for_block(self, exam_id: str, segment: str, method: str) -> list[QCReview]:
        """All the QCs kept for one block (exam x segment x method), in any order. Empty list if none."""
        ...
