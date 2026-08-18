"""
JSON Writer — concrete class
"""

from pathlib import Path

from medical_report.models.domain  import Exam
from results_writer.writer_interface import WriterInterface

class JsonWriter(WriterInterface):
    """Writes an Exam domain object to a JSON file."""

    def write(self, exam: Exam, destination: Path) -> Path:
        """Serialize the Exam to JSON and write to destination. Returns the file path written."""
        if destination.is_dir() or not destination.suffix:
            filename = f"{exam.metadata.exam_id}_{exam.metadata.exam_date}_{exam.metadata.segment}_{exam.metadata.method}_{exam.metadata.version}_{exam.metadata.acquisition}.json"
            destination = destination / filename
        data = exam.model_dump_json(exclude_none=True, indent=2)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with open(destination, "w", encoding="utf-8") as f:
            f.write(data)
        return destination
