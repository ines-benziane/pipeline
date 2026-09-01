"""Writer interface — abstract port for data persistence."""

from abc import ABC, abstractmethod
from pathlib import Path
from medical_report.models.domain import Exam
from runner.method import QCUserDecisions


class WriterInterface(ABC):
    """Abstract writer — defines what any persistence adapter must do."""

    @abstractmethod
    def write(self, exam: Exam, destination: Path, decision: QCUserDecisions | None = None) -> Path:
        """Persist an Exam to the given destination. Returns the path written."""
        ...
