"""run_job: drives one job through a method and records its state."""

import logging
from pathlib import Path

import pytest

from runner import job_store, methods_registry
from runner.job import Job, JobState
from runner.job_runner import run_job
from runner.method import Method, QCCheckpoint, Result


class RecordingMethod(Method):
    """Configurable fake: `behaviour` is "ok", "checkpoint" or "crash"."""
    name = "recording"
    version = "0"
    comparability_criteria = []
    CHECKPOINTS = ("stage1",)
    behaviour = "ok"
    calls = []

    def _result(self, workdir):
        output = Path(workdir) / "recording_result.json"
        output.write_text("{}", encoding="utf-8")
        return Result(results=output, auto_valid=True, provenance={"name": self.name})

    def run(self, source_dir, exam_id, workdir, segment, series, params, date, qc, qc_dir,
            decision=None, debug=False, action=None, multicenter=False, seg_series=None):
        RecordingMethod.calls.append(("run", {"qc": qc, "decision": decision}))
        if self.behaviour == "checkpoint":
            raise QCCheckpoint("stage1")
        if self.behaviour == "crash":
            raise RuntimeError("unusable data")
        return self._result(workdir)

    def handle_checkpoint(self, *, name, workdir, segment, exam_id, qc, qc_dir=None,
                          decision=None, debug=False, multicenter=False, seg_series=None):
        RecordingMethod.calls.append(("handle_checkpoint", {"name": name, "qc": qc, "decision": decision}))
        return self._result(workdir)


@pytest.fixture(autouse=True)
def _fresh_method(monkeypatch):
    monkeypatch.setattr(RecordingMethod, "behaviour", "ok")
    monkeypatch.setattr(RecordingMethod, "calls", [])
    methods_registry.register(RecordingMethod)


def _job(**overrides):
    kwargs = dict(exam_id="EXAM001", source_dir="src", segment="legs",
                  method_name="recording", series=[17, 18])
    kwargs.update(overrides)
    return Job(**kwargs)


def test_success_copies_result_and_marks_ready(isolated_store, tmp_path):
    job = run_job(_job(), tmp_path / "out")

    assert job.state is JobState.RESULTS_READY
    assert (isolated_store / "recording_result.json").exists()
    assert job_store.load(job.job_id).state is JobState.RESULTS_READY


def test_qc_checkpoint_suspends_and_records_stage(isolated_store, tmp_path):
    RecordingMethod.behaviour = "checkpoint"
    job = run_job(_job(qc="checkpoint"), tmp_path / "out")

    assert job.state is JobState.SUSPENDED
    assert job.checkpoint == "stage1"
    assert job_store.load(job.job_id).checkpoint == "stage1"
    assert not isolated_store.exists()


def test_method_failure_marks_failed_and_produces_nothing(isolated_store, tmp_path):
    RecordingMethod.behaviour = "crash"
    job = _job()
    with pytest.raises(RuntimeError):
        run_job(job, tmp_path / "out")

    assert job_store.load(job.job_id).state is JobState.FAILED
    assert not isolated_store.exists()


def test_job_with_checkpoint_resumes_instead_of_rerunning(isolated_store, tmp_path):
    run_job(_job(checkpoint="stage1"), tmp_path / "out")

    assert [c[0] for c in RecordingMethod.calls] == ["handle_checkpoint"]
    assert RecordingMethod.calls[0][1]["name"] == "stage1"


def test_default_qc_dir_is_created_under_output_dir(isolated_store, tmp_path):
    job = run_job(_job(), tmp_path / "out")

    assert Path(job.qc_dir) == tmp_path / "out" / job.job_id
    assert Path(job.qc_dir).is_dir()


def test_given_qc_dir_is_kept(isolated_store, tmp_path):
    job = run_job(_job(qc_dir=tmp_path / "my_qc"), tmp_path / "out")

    assert Path(job.qc_dir) == tmp_path / "my_qc"


def test_run_log_written_in_workdir(isolated_store, tmp_path):
    job = run_job(_job(), tmp_path / "out")

    assert (job.workdir / "run.log").exists()


@pytest.mark.parametrize("behaviour", ["ok", "checkpoint", "crash"])
def test_log_handler_removed_whatever_the_outcome(isolated_store, tmp_path, behaviour):
    """No leaked file handler: the next job must not log into this job's run.log."""
    RecordingMethod.behaviour = behaviour
    before = list(logging.getLogger().handlers)
    try:
        run_job(_job(), tmp_path / "out")
    except RuntimeError:
        pass
    assert logging.getLogger().handlers == before
