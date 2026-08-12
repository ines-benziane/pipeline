from runner.result_index import ResultIndex
from runner.job_runner import RESULT_DIR


class FileResultIndex(ResultIndex):
    def has_result(self, exam_id) -> bool:
        return any(RESULT_DIR.glob(f"{exam_id}_*.json"))