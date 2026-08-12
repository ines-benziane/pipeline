import pytest
from pathlib import Path

from runner.pipeline import run_pipeline
from runner.exam_catalog import ExamSummary
from runner.method import Method, Result
from runner import methods_registry


class FakeCatalog:
    def __init__(self, related=None):
        self.related = related or []

    def find_exams(self, patient_name):
        return [
            ExamSummary(exam_id="EXAM001", patient_name=patient_name, exam_date="20200101", description="fake"),
            ExamSummary(exam_id="EXAM001", patient_name=patient_name, exam_date="20200101", description="fake"),
        ]

    def find_related_exams(self, exam_id):
        return self.related


class FakeRetriever:
    def __init__(self):
        self.calls = []

    def retrieve_exam(self, exam_id, dest_dir, *, mode):
        self.calls.append(exam_id)


class FakeReportGenerator:
    def __init__(self):
        self.report = []

    def generate(self, exam_ids, data_dir, output_dir, *, lang="en", config=None):
        self.report.append(exam_ids)
        return Path("fake.pdf")


class FakeResultIndex:
    def __init__(self, already_present=()):
        self.already_present = set(already_present)

    def has_result(self, exam_id):
        return exam_id in self.already_present


class FakeMethod(Method):
    name = "fake"
    version = "0"
    comparability_criteria = []

    def run(self, exam_dir, workdir, segment):
        output = Path(workdir) / "fake_result.json"
        output.write_text("{}", encoding="utf-8")
        return Result(results=output, auto_valid=True, provenance={"name": self.name})


@pytest.fixture(autouse=True)
def _register_fake_method():
    methods_registry.register(FakeMethod)


@pytest.fixture(autouse=True)
def _isolate_disk(tmp_path, monkeypatch):
    """Empêche run_job/job_store d'écrire dans les vrais data/results, data/jobs, workdirs."""
    results_dir = tmp_path / "results"
    monkeypatch.setattr("runner.job_runner.RESULT_DIR", results_dir)
    monkeypatch.setattr("runner.pipeline.RESULT_DIR", results_dir)
    monkeypatch.setattr("runner.job_runner.WORKDIR_ROOT", tmp_path / "workdirs")
    monkeypatch.setattr("runner.job_store.JOBS_DIR", tmp_path / "jobs")


def test_ambiguous_patient_raises():
    """0 ou plusieurs matches patient+date -> erreur explicite, jamais un choix silencieux."""
    with pytest.raises(ValueError):
        run_pipeline(
            result_index=None,
            retriever=None,
            report_generator=None,
            catalog=FakeCatalog(),
            with_antecedent=False,
            dest_dir=None,
            mode=None,
            method=None,
            output_dir=None,
            patient_name="John Doe",
            exam_date="20200101",
        )


def test_happy_path_without_antecedent(tmp_path):
    """Sans with_antecedent, un seul retrieve et un rapport sur un seul exam_id."""
    retriever = FakeRetriever()
    report_generator = FakeReportGenerator()

    result = run_pipeline(
        result_index=FakeResultIndex(),
        retriever=retriever,
        report_generator=report_generator,
        catalog=FakeCatalog(),
        with_antecedent=False,
        dest_dir=tmp_path / "dicom_in",
        mode="anonymize",
        method="fake",
        output_dir=tmp_path / "out",
        exam_id="EXAM001",
        segment=["legs"],
    )

    assert retriever.calls == ["EXAM001"]
    assert report_generator.report == [["EXAM001"]]
    assert result["exam_ids_for_report"] == ["EXAM001"]


def test_with_antecedent_not_yet_processed(tmp_path):
    """Antécédent absent du result_index -> il est retrieve+run aussi, puis inclus au rapport."""
    retriever = FakeRetriever()
    report_generator = FakeReportGenerator()
    antecedent = ExamSummary(exam_id="ANTEC001", patient_name="John Doe", exam_date="20200101", description="fake")

    run_pipeline(
        result_index=FakeResultIndex(already_present=()),
        retriever=retriever,
        report_generator=report_generator,
        catalog=FakeCatalog(related=[antecedent]),
        with_antecedent=True,
        dest_dir=tmp_path / "dicom_in",
        mode="anonymize",
        method="fake",
        output_dir=tmp_path / "out",
        exam_id="EXAM001",
        segment=["legs"],
    )

    assert retriever.calls == ["EXAM001", "ANTEC001"]
    assert report_generator.report == [["EXAM001", "ANTEC001"]]


def test_with_antecedent_already_processed(tmp_path):
    """Antécédent déjà présent dans le result_index -> pas retraité, seul l'exam du jour est retrieve."""
    retriever = FakeRetriever()
    report_generator = FakeReportGenerator()
    antecedent = ExamSummary(exam_id="ANTEC001", patient_name="John Doe", exam_date="20200101", description="fake")

    run_pipeline(
        result_index=FakeResultIndex(already_present=("ANTEC001",)),
        retriever=retriever,
        report_generator=report_generator,
        catalog=FakeCatalog(related=[antecedent]),
        with_antecedent=True,
        dest_dir=tmp_path / "dicom_in",
        mode="anonymize",
        method="fake",
        output_dir=tmp_path / "out",
        exam_id="EXAM001",
        segment=["legs"],
    )

    assert retriever.calls == ["EXAM001"]
    assert report_generator.report == [["EXAM001", "ANTEC001"]]


def test_no_related_exam_raises(tmp_path):
    """with_antecedent=True mais aucun exam lié trouvé -> erreur explicite."""
    with pytest.raises(ValueError):
        run_pipeline(
            result_index=FakeResultIndex(),
            retriever=FakeRetriever(),
            report_generator=FakeReportGenerator(),
            catalog=FakeCatalog(related=[]),
            with_antecedent=True,
            dest_dir=tmp_path / "dicom_in",
            mode="anonymize",
            method="fake",
            output_dir=tmp_path / "out",
            exam_id="EXAM001",
            segment=["legs"],
        )
