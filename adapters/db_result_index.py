from runner.result_index import ResultIndex

class DbResultIndex(ResultIndex):
    def has_result(self, exam_id) -> bool :
        raise NotImplementedError("DB pas encore branchée")