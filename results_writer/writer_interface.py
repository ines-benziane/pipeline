"""Writer interface — abstract port for data persistence."""

from abc import ABC, abstractmethod
from pathlib import Path
from medical_report.models.domain import Exam


class WriterInterface(ABC):
    """Abstract writer — defines what any persistence adapter must do."""

    @abstractmethod
    def write(self, exam: Exam, destination: Path) -> Path:
        """Persist an Exam to the given destination. Returns the path written."""
        ...
