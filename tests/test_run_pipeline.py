import pytest
import yaml
from pathlib import Path

from runner.pipeline import run_pipeline
from runner.exam_catalog import AmbiguousExamError, ExamSummary, NoExamForPatientError
from runner.job import JobState
from runner.method import Method, QCCheckpoint, Result
from runner import job_store, methods_registry


class FakeCatalog:
    def __init__(self, exams=()):
        self.exams = list(exams)
        self.calls = []

    def find_exams(self, patient_name):
        self.calls.append(patient_name)
        return self.exams


class FakeMethod(Method):
    """auto_valid=True -> job RESULTS_READY. Remembers the args it was run with."""
    name = "fake"
    version = "0"
    comparability_criteria = []
    last_call = None

    def run(self, ctx):
        FakeMethod.last_call = {"exam_id": ctx.exam_id, "segment": ctx.segment, "series": ctx.series,
                                "params": ctx.params, "date": ctx.exam_date, "qc": ctx.qc}
        output = Path(ctx.workdir) / "fake_result.json"
        output.write_text("{}", encoding="utf-8")
        return Result(results=output, auto_valid=True, provenance={"name": self.name})

    def handle_checkpoint(self, *, name, workdir, segment, exam_id, qc, qc_dir=None,
                          decision=None, debug=False, multicenter=False, seg_series=None):
        raise NotImplementedError


class CheckpointMethod(FakeMethod):
    """Pauses for QC at its first stage."""
    name = "fake_checkpoint"
    CHECKPOINTS = ("stage1",)

    def run(self, *args, **kwargs):
        raise QCCheckpoint(self.CHECKPOINTS[0])


class CrashingMethod(FakeMethod):
    """Fails like a method fed with unusable data."""
    name = "fake_crash"

    def run(self, *args, **kwargs):
        raise RuntimeError("unusable data")


@pytest.fixture(autouse=True)
def _register_fake_methods():
    for m in (FakeMethod, CheckpointMethod, CrashingMethod):
        methods_registry.register(m)


@pytest.fixture(autouse=True)
def _isolate_disk(tmp_path, monkeypatch):
    """Empêche run_job/job_store d'écrire dans les vrais workdirs."""
    results_dir = tmp_path / "results"
    monkeypatch.setattr("runner.job_runner.RESULT_DIR", results_dir)
    monkeypatch.setattr("runner.pipeline.RESULT_DIR", results_dir)
    monkeypatch.setattr("runner.job_runner.WORKDIR_ROOT", tmp_path / "workdirs")
    monkeypatch.setattr("runner.job_store.JOBS_DIR", tmp_path / "jobs")
    return results_dir


def _run(tmp_path, *, method="fake", params=None, **overrides):
    source_dir = tmp_path / "source"
    source_dir.mkdir(exist_ok=True)
    kwargs = dict(
        catalog=FakeCatalog(),
        source_dir=str(source_dir),
        acquisition_id={"1.0": {"legs": None}},
        method=(method, params or {}),
        output_dir=tmp_path / "out",
        series=[17, 18],
        qc="off",
        exam_id="EXAM001",
    )
    kwargs.update(overrides)
    return run_pipeline(**kwargs)


def test_happy_path_with_exam_id(tmp_path, _isolate_disk):
    """exam_id fourni -> catalogue non consulté, job terminé, résultat copié dans RESULT_DIR."""
    catalog = FakeCatalog()
    outcome = _run(tmp_path, catalog=catalog)

    assert outcome.status == "done"
    assert outcome.exam_id == "EXAM001"
    assert catalog.calls == []
    assert (_isolate_disk / "fake_result.json").exists()
    assert job_store.load(outcome.job_id).state is JobState.RESULTS_READY


def test_job_receives_parsed_inputs(tmp_path):
    """Segment, séries, paramètres et date arrivent tels quels à la méthode."""
    _run(tmp_path, params={"k": "v"}, exam_date="20260112",
         acquisition_id={"1.0": {"thighs": "L"}})

    assert FakeMethod.last_call == {"exam_id": "EXAM001", "segment": "thighs", "series": [17, 18],
                                    "params": {"k": "v"}, "date": "20260112", "qc": "off"}


def test_series_selection_written_to_source_dir(tmp_path):
    """Les séries choisies sont tracées dans source_dir/series_selection.yml."""
    _run(tmp_path, series=[17, 18])

    written = yaml.safe_load((tmp_path / "source" / "series_selection.yml").read_text())
    assert written == [17, 18]


def test_no_series_writes_no_selection_file(tmp_path):
    _run(tmp_path, series=None)

    assert not (tmp_path / "source" / "series_selection.yml").exists()


def test_exam_resolved_from_patient_and_date(tmp_path):
    """Sans exam_id, un seul exam patient+date -> son exam_id est utilisé."""
    catalog = FakeCatalog([
        ExamSummary(exam_id="EXAM_A", patient_name="John Doe", exam_date="20200101", description="fake"),
        ExamSummary(exam_id="EXAM_B", patient_name="John Doe", exam_date="20210101", description="fake"),
    ])
    outcome = _run(tmp_path, catalog=catalog, exam_id=None,
                   patient_name="John Doe", exam_date="20200101")

    assert outcome.exam_id == "EXAM_A"


def test_no_exam_for_patient_raises(tmp_path):
    """Aucun exam patient+date -> erreur explicite, avec un hint."""
    catalog = FakeCatalog([
        ExamSummary(exam_id="EXAM_B", patient_name="John Doe", exam_date="20210101", description="fake"),
    ])
    with pytest.raises(NoExamForPatientError) as exc:
        _run(tmp_path, catalog=catalog, exam_id=None, patient_name="John Doe", exam_date="20200101")
    assert exc.value.hint


def test_ambiguous_patient_raises(tmp_path):
    """Plusieurs exams patient+date -> erreur explicite, jamais un choix silencieux."""
    catalog = FakeCatalog([
        ExamSummary(exam_id="EXAM_A", patient_name="John Doe", exam_date="20200101", description="fake"),
        ExamSummary(exam_id="EXAM_A2", patient_name="John Doe", exam_date="20200101", description="fake"),
    ])
    with pytest.raises(AmbiguousExamError) as exc:
        _run(tmp_path, catalog=catalog, exam_id=None, patient_name="John Doe", exam_date="20200101")
    assert exc.value.hint


def test_qc_checkpoint_suspends(tmp_path, _isolate_disk):
    """Méthode en pause QC -> outcome suspended, checkpoint et qc_dir renseignés, aucun résultat."""
    outcome = _run(tmp_path, method="fake_checkpoint", qc="checkpoint")

    assert outcome.status == "suspended"
    assert outcome.checkpoint == "stage1"
    assert outcome.qc_dir is not None and Path(outcome.qc_dir).is_dir()
    assert job_store.load(outcome.job_id).state is JobState.SUSPENDED
    assert not _isolate_disk.exists() or not any(_isolate_disk.iterdir())


def test_qc_dir_is_created(tmp_path):
    qc_dir = tmp_path / "qc"
    _run(tmp_path, qc_dir=qc_dir)

    assert qc_dir.is_dir()


def test_failing_method_produces_no_result(tmp_path, _isolate_disk):
    """Méthode en échec -> l'erreur remonte, job FAILED, aucun fichier résultat."""
    with pytest.raises(RuntimeError):
        _run(tmp_path, method="fake_crash")

    jobs = [job_store.load(p.stem) for p in (tmp_path / "jobs").glob("*.json")]
    assert [j.state for j in jobs] == [JobState.FAILED]
    assert not _isolate_disk.exists() or not any(_isolate_disk.iterdir())
