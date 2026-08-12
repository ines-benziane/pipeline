from runner.exam_catalog import ExamCatalog, ExamSummary, SeriesSummary

class DummyExamCatalog(ExamCatalog) :
    def find_exams(self, patient_name):
        return [
            ExamSummary(
                exam_id="EXAM001",
                patient_name=patient_name,
                exam_date="20200101",
                description="Fake exam for testing",
            )
        ]
    
    def find_related_exams(self, exam_id):
        return [
            ExamSummary(
                exam_id = "ANTEC001",
                patient_name = "John Doe",
                exam_date = "20200101",
                description="Fake antecedent for testing",

            )

        ]
    
    def show_series(self, exam_id):
        return [
            SeriesSummary(
                description = "VIBE testing",
                series_id = "testing series",
            )
        ]