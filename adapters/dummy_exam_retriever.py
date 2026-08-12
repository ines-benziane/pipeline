from runner.exam_retriever import ExamRetriever, ExamRetrievalResult, RetrievedSeries, DeidentificationMode
from pathlib import Path
import shutil
from datetime import datetime

class DummyExamRetriever(ExamRetriever):
    def __init__(self, source_dir):
        self.source_dir = Path(source_dir)

    def retrieve_exam(self, exam_id, destination_dir, *, mode, config=None):
        destination_dir = Path(destination_dir)
        shutil.copytree(self.source_dir, destination_dir, dirs_exist_ok=True)
        file_count = len(list(destination_dir.iterdir())) 
        retrieved_series = RetrievedSeries(series_id="S01", number_of_files=file_count, series_directory=destination_dir)
        return ExamRetrievalResult(exam_id = exam_id, destination_dir = destination_dir, series_retrieved = [retrieved_series], deidentification_mode=mode, time=datetime.now())
